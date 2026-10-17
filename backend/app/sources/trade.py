from __future__ import annotations

import calendar
import html
import json
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx

from app.config import get_settings


TRADE_SOURCE_KEY = "commerce_monthly_trade"
TRADE_REPORT_PATH = "/tag/monthly_trade_us"
TRADE_UPDATE_PATH = "/livewire-da76d7be/update"
TRADE_UNIT = "USD billion"
TRADE_INDICATORS = {
    "exports_india": "Exports — India",
    "imports_india": "Imports — India",
    "trade_balance_india": "Imports, Exports and Trade Balance",
}


class TradeSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class TradePageBootstrap:
    csrf_token: str
    snapshot: str
    update_path: str


@dataclass(frozen=True)
class MonthlyTradePoint:
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
            http2=True,
            headers={
                "Accept": "text/html,application/json",
                "User-Agent": settings.nse_user_agent,
            },
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_recent_monthly_trade(self, months: int = 6) -> list[MonthlyTradePoint]:
        """Return the recent validated monthly series needed by the dashboard chart."""

        if months < 2 or months > 12:
            raise ValueError("Trade history must contain between 2 and 12 months.")
        if self._cache is not None:
            cached_at, point = self._cache
            if time.monotonic() - cached_at < self._cache_seconds:
                return point

        try:
            response = await self._client.get(TRADE_REPORT_PATH)
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise TradeSourceError(
                "Department of Commerce trade report request returned "
                f"HTTP {error.response.status_code}."
            ) from error
        except httpx.HTTPError as error:
            raise TradeSourceError("Department of Commerce trade report request failed.") from error

        bootstrap = parse_trade_page_bootstrap(response.text)
        months_to_try = _recent_months(date.today(), count=months + 1)
        errors: list[str] = []
        points: dict[date, MonthlyTradePoint] = {}
        for month in months_to_try:
            try:
                point = await self._fetch_month(bootstrap, month)
            except TradeSourceError as error:
                errors.append(str(error))
                continue
            points[point.observation_date] = point
            if len(points) >= months:
                break

        if not points:
            detail = "; ".join(errors[-2:])
            raise TradeSourceError(
                "Department of Commerce trade report has no usable recent monthly data."
                + (f" {detail}" if detail else "")
            )
        history = sorted(points.values(), key=lambda item: item.observation_date)
        self._cache = (time.monotonic(), history)
        return history

    async def fetch_latest_monthly_trade(self) -> MonthlyTradePoint:
        """Compatibility helper for callers that require only the newest point."""

        return (await self.fetch_recent_monthly_trade(months=2))[-1]

    async def _fetch_month(self, bootstrap: TradePageBootstrap, month: int) -> MonthlyTradePoint:
        payload = {
            "_token": bootstrap.csrf_token,
            "components": [
                {
                    "snapshot": bootstrap.snapshot,
                    "updates": {"MonthUs": str(month)},
                    "calls": [],
                }
            ],
        }
        try:
            response = await self._client.post(
                bootstrap.update_path,
                json=payload,
                headers={
                    "Referer": str(self._client.base_url.join(TRADE_REPORT_PATH)),
                    "X-Livewire": "true",
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise TradeSourceError(
                "Department of Commerce trade update request returned "
                f"HTTP {error.response.status_code}."
            ) from error
        except httpx.HTTPError as error:
            raise TradeSourceError("Department of Commerce trade update request failed.") from error

        try:
            response_payload = response.json()
            report_html = response_payload["components"][0]["effects"]["html"]
        except (KeyError, TypeError, ValueError) as error:
            raise TradeSourceError("Department of Commerce returned an invalid trade update.") from error
        if not isinstance(report_html, str):
            raise TradeSourceError("Department of Commerce trade update has no report HTML.")
        return parse_monthly_trade_html(report_html, requested_month=month)


def parse_trade_page_bootstrap(page_html: str) -> TradePageBootstrap:
    csrf_match = re.search(r'data-csrf=["\']([^"\']+)["\']', page_html, re.IGNORECASE)
    snapshot_match = re.search(r'wire:snapshot=["\'](.*?)["\']', page_html, re.IGNORECASE)
    update_match = re.search(r'data-update-uri=["\']([^"\']+)["\']', page_html, re.IGNORECASE)
    if csrf_match is None or snapshot_match is None:
        raise TradeSourceError("Department of Commerce trade page is missing Livewire bootstrap data.")

    snapshot = html.unescape(snapshot_match.group(1))
    try:
        json.loads(snapshot)
    except ValueError as error:
        raise TradeSourceError("Department of Commerce trade page has an invalid Livewire snapshot.") from error

    return TradePageBootstrap(
        csrf_token=html.unescape(csrf_match.group(1)),
        snapshot=snapshot,
        update_path=html.unescape(update_match.group(1)) if update_match else TRADE_UPDATE_PATH,
    )


def parse_monthly_trade_html(report_html: str, requested_month: int) -> MonthlyTradePoint:
    if requested_month not in range(1, 13):
        raise TradeSourceError("Requested trade month must be between 1 and 12.")
    report_date = _parse_report_date(report_html)
    rows = _table_rows(report_html)
    points: list[MonthlyTradePoint] = []
    for cells in rows:
        if len(cells) != 8 or not cells[0].isdigit():
            continue
        try:
            observation_date = _observation_date(cells[1], requested_month)
            exports = _parse_amount(cells[2])
            imports = _parse_amount(cells[4])
            reported_balance = _parse_amount(cells[6])
        except ValueError as error:
            raise TradeSourceError("Department of Commerce trade row contains an invalid value.") from error
        if observation_date > report_date:
            continue
        calculated_balance = exports - imports
        if abs(calculated_balance - reported_balance) > 0.01:
            raise TradeSourceError("Department of Commerce trade balance does not match exports minus imports.")
        points.append(
            MonthlyTradePoint(
                period_label=f"{calendar.month_abbr[requested_month]} {observation_date.year}",
                observation_date=observation_date,
                source_as_of_date=report_date,
                exports_usd_millions=exports,
                imports_usd_millions=imports,
                reported_trade_balance_usd_millions=reported_balance,
                raw_payload={
                    "report_date": report_date.isoformat(),
                    "month": calendar.month_name[requested_month],
                    "year": cells[1],
                    "exports_usd_millions": exports,
                    "imports_usd_millions": imports,
                    "reported_trade_balance_usd_millions": reported_balance,
                    "source_unit": "USD million",
                },
            )
        )
    if not points:
        raise TradeSourceError("Department of Commerce trade report has no data rows for this month.")
    return max(points, key=lambda point: point.observation_date)


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


def _parse_report_date(report_html: str) -> date:
    match = re.search(r"Report\s+Dated:\s*([A-Za-z]{3},\s*[A-Za-z]{3}\s+\d{1,2},\s*\d{4})", report_html)
    if match is None:
        raise TradeSourceError("Department of Commerce trade report is missing its report date.")
    try:
        return datetime.strptime(match.group(1), "%a, %b %d, %Y").date()
    except ValueError as error:
        raise TradeSourceError("Department of Commerce trade report date is invalid.") from error


def _observation_date(year_label: str, month: int) -> date:
    match = re.search(r"(\d{4})(?:\s*-\s*(\d{2,4}))?", year_label)
    if match is None:
        raise ValueError("year label is invalid")
    first_year = int(match.group(1))
    second_year_text = match.group(2)
    if second_year_text is None:
        year = first_year
    else:
        second_year = int(second_year_text)
        if second_year < 100:
            second_year = (first_year // 100) * 100 + second_year
        year = first_year if month >= 4 else second_year
    return date(year, month, calendar.monthrange(year, month)[1])


def _parse_amount(value: str) -> float:
    normalized = value.replace(",", "").replace("₹", "").replace("$", "").strip()
    if not normalized or normalized in {"-", "—", "NA", "N/A"}:
        raise ValueError("amount is empty")
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = "-" + normalized[1:-1]
    return float(normalized)


def _recent_months(today: date, count: int) -> list[int]:
    return [((today.month - offset - 1) % 12) + 1 for offset in range(count)]
