from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from app.config import get_settings


TRADE_SOURCE_KEY = "commerce_monthly_trade"
TRADE_REPORT_PATH = "/eidb/chapter_wise_all_commodities_export"
TRADE_UNIT = "USD billion"
TRADE_INDICATORS = {
    "exports_india": "Exports — India",
    "imports_india": "Imports — India",
    "trade_balance_india": "Imports, Exports and Trade Balance",
}

_EXPORT_PATH = "/eidb/chapter_wise_all_commodities_export"
_IMPORT_PATH = "/eidb/chapter_wise_all_commodities_import"
_ANOMALY_RATIO = 1.6


class TradeSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class MonthlyTradePoint:
    """One fiscal year's total trade. Named for API compatibility with callers/tests."""

    period_label: str
    observation_date: date
    source_as_of_date: date
    exports_usd_millions: float
    imports_usd_millions: float
    reported_trade_balance_usd_millions: float
    raw_payload: dict[str, Any]


class TradeClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
        cache_seconds: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self._cache_seconds = cache_seconds or settings.trade_cache_seconds
        self._cache: tuple[float, list[MonthlyTradePoint]] | None = None
        self._client = httpx.AsyncClient(
            base_url=base_url or settings.trade_base_url,
            timeout=timeout_seconds or settings.request_timeout_seconds,
            follow_redirects=True,
            headers={
                "Accept": "text/html,application/json",
                "User-Agent": settings.nse_user_agent,
            },
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_recent_monthly_trade(self, months: int = 6) -> list[MonthlyTradePoint]:
        """Return the recent validated fiscal-year trade totals needed by the dashboard chart.

        The Department of Commerce's "Monthly Trade" Livewire report (the
        original source for this adapter) has not had any usable rows for any
        month since roughly mid-2024 (see readme.md). The EIDB chapter-wise
        commodity breakdown on the same site is, by contrast, kept current
        (through FY 2025-2026) — each fiscal-year point here is the sum of all
        ~98 HS chapters' export and import values for that year. The parameter
        is still named "months" for compatibility with existing callers/tests;
        it is clamped and used as a count of fiscal years.
        """

        years = min(max(months, 2), 8)
        if self._cache is not None:
            cached_at, points = self._cache
            if time.monotonic() - cached_at < self._cache_seconds:
                return points

        fiscal_years = _recent_fiscal_years(count=years)
        fetched: list[MonthlyTradePoint] = []
        errors: list[str] = []
        for fiscal_year in fiscal_years:
            try:
                exports = await self._fetch_chapter_total(_EXPORT_PATH, fiscal_year)
                imports = await self._fetch_chapter_total(_IMPORT_PATH, fiscal_year)
            except TradeSourceError as error:
                errors.append(str(error))
                continue
            fetched.append(_build_point(fiscal_year, exports, imports))

        points = _drop_anomalous_points(fetched)
        if not points:
            detail = "; ".join(errors[-2:])
            raise TradeSourceError(
                "Department of Commerce EIDB trade report has no usable recent annual data."
                + (f" {detail}" if detail else "")
            )
        points.sort(key=lambda point: point.observation_date)
        self._cache = (time.monotonic(), points)
        return points

    async def fetch_latest_monthly_trade(self) -> MonthlyTradePoint:
        """Compatibility helper for callers that require only the newest point."""

        return (await self.fetch_recent_monthly_trade(months=2))[-1]

    async def _fetch_chapter_total(self, path: str, fiscal_year: int) -> float:
        try:
            page = await self._client.get(path)
            page.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise TradeSourceError(
                f"Department of Commerce EIDB page request returned HTTP {error.response.status_code}."
            ) from error
        except httpx.HTTPError as error:
            raise TradeSourceError("Department of Commerce EIDB page request failed.") from error

        token = _extract_csrf_token(page.text)
        year_field, report_field, chapter_field = _form_field_names(page.text)

        try:
            response = await self._client.post(
                path,
                data={
                    "_token": token,
                    "level": "2",
                    year_field: str(fiscal_year),
                    report_field: "2",  # US $ Million
                    chapter_field: "all",
                },
                headers={"Referer": str(self._client.base_url.join(path))},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise TradeSourceError(
                f"Department of Commerce EIDB update request returned HTTP {error.response.status_code}."
            ) from error
        except httpx.HTTPError as error:
            raise TradeSourceError("Department of Commerce EIDB update request failed.") from error

        return _sum_selected_year_column(response.text)


def _extract_csrf_token(page_html: str) -> str:
    match = re.search(r'name=["\']_token["\']\s+value=["\']([^"\']+)["\']', page_html, re.IGNORECASE)
    if match is None:
        match = re.search(
            r'<input[^>]*value=["\']([^"\']+)["\'][^>]*name=["\']_token["\']', page_html, re.IGNORECASE
        )
    if match is None:
        raise TradeSourceError("Department of Commerce EIDB page is missing its CSRF token.")
    return html.unescape(match.group(1))


def _form_field_names(page_html: str) -> tuple[str, str, str]:
    selects = re.findall(r'<select[^>]*name=["\']([^"\']+)["\']', page_html, re.IGNORECASE)
    year_field = next((name for name in selects if "year" in name.lower()), None)
    report_field = next((name for name in selects if "report" in name.lower()), None)
    chapter_field = next((name for name in selects if "chapter" in name.lower()), None)
    if not (year_field and report_field and chapter_field):
        raise TradeSourceError("Department of Commerce EIDB page is missing its expected form fields.")
    return year_field, report_field, chapter_field


def _sum_selected_year_column(report_html: str) -> float:
    """Sum the HS-chapter rows' value for the requested fiscal year.

    The response table always shows two value columns (the requested year and
    the prior year); the requested year is always the second one, immediately
    followed by a "%Share" column, matching whichever year was posted.
    """

    rows = _table_rows(report_html)
    if not rows:
        raise TradeSourceError("Department of Commerce EIDB report has no HS-chapter rows.")
    total = 0.0
    counted = 0
    for cells in rows:
        if len(cells) < 6 or not cells[0].isdigit():
            continue
        try:
            total += _parse_amount(cells[5])
        except ValueError:
            continue
        counted += 1
    if counted < 50:
        raise TradeSourceError("Department of Commerce EIDB report has too few HS-chapter rows to trust.")
    return total


def _table_rows(report_html: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", report_html, flags=re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, flags=re.IGNORECASE | re.DOTALL)
        if cells:
            rows.append([_plain_text(cell) for cell in cells])
    return rows


def _plain_text(value: str) -> str:
    without_comments = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_comments)
    return " ".join(html.unescape(without_tags).replace("\xa0", " ").split())


def _parse_amount(value: str) -> float:
    normalized = value.replace(",", "").strip()
    if not normalized or normalized in {"-", "—", "NA", "N/A"}:
        raise ValueError("amount is empty")
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = "-" + normalized[1:-1]
    return float(normalized)


def _build_point(fiscal_year: int, exports: float, imports: float) -> MonthlyTradePoint:
    fy_end = date(fiscal_year + 1, 3, 31)
    label = f"FY{fiscal_year}-{(fiscal_year + 1) % 100:02d}"
    return MonthlyTradePoint(
        period_label=label,
        observation_date=fy_end,
        source_as_of_date=fy_end,
        exports_usd_millions=exports,
        imports_usd_millions=imports,
        reported_trade_balance_usd_millions=exports - imports,
        raw_payload={
            "fiscal_year": f"{fiscal_year}-{fiscal_year + 1}",
            "exports_usd_millions": exports,
            "imports_usd_millions": imports,
            "hs_chapters_summed": 98,
        },
    )


def _drop_anomalous_points(points: list[MonthlyTradePoint]) -> list[MonthlyTradePoint]:
    """Drop a fiscal year whose total implausibly diverges from the rest of the series.

    Live verification found that the EIDB chapter-wise view currently reports
    an export/import total for one fiscal year at roughly double the value
    shown for that same year everywhere else on the site — a government-side
    data anomaly, not a parsing bug. A collector must not store a figure it
    can show is implausible, so any point whose export or import total is
    more than ``_ANOMALY_RATIO`` away from the *median* of the series is
    excluded rather than stored. With fewer than three points there is no
    reliable majority to compare against, so nothing is dropped.
    """

    if len(points) < 3:
        return list(points)

    export_median = _median(point.exports_usd_millions for point in points)
    import_median = _median(point.imports_usd_millions for point in points)
    return [
        point
        for point in points
        if not _is_anomalous(point.exports_usd_millions, export_median)
        and not _is_anomalous(point.imports_usd_millions, import_median)
    ]


def _median(values: Any) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _is_anomalous(value: float, reference: float) -> bool:
    if reference <= 0:
        return False
    ratio = value / reference
    return ratio > _ANOMALY_RATIO or ratio < (1 / _ANOMALY_RATIO)


def _recent_fiscal_years(count: int) -> list[int]:
    today = date.today()
    current_fiscal_year = today.year if today.month >= 4 else today.year - 1
    return [current_fiscal_year - offset for offset in range(count)]
