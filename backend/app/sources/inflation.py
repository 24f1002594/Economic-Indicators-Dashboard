from __future__ import annotations

import calendar
import io
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import get_settings


MOSPI_CPI_SOURCE_KEY = "mospi_cpi"
MOSPI_RELEASES_PATH = "/api/latest-release/get-web-latest-release-list"
INFLATION_INDICATOR_ID = "inflation_india"
INFLATION_UNIT = "%"
RBI_TARGET_PERCENT = 4.0
RBI_TARGET_BAND = "2%–6%"
RBI_TARGET_SOURCE_URL = "https://www.rbi.org.in/commonperson/English/Scripts/speeches.aspx?Id=3161"
_RELEASE_PERIOD_PATTERN = re.compile(
    r"CPI.*?month\s+of\s+([A-Za-z]+)\s*,?\s*(\d{4})", re.IGNORECASE
)
_INFLATION_PATTERN = re.compile(
    r"Year-on-year\s+inflation\s+rate\s+based\s+on\s+All\s+India\s+Consumer\s+Price\s+"
    r"Index\s+\(CPI\).*?\s+is\s+(-?\d+(?:\.\d+)?)%",
    re.IGNORECASE | re.DOTALL,
)


class InflationSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class MospiCpiRelease:
    title: str
    reference_period: date
    release_date: date
    pdf_url: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class CpiInflationPoint:
    period_label: str
    observation_date: date
    source_as_of_date: date
    inflation_percent: float
    raw_payload: dict[str, Any]


class InflationClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
        cache_seconds: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self._cache_seconds = cache_seconds or settings.mospi_cpi_cache_seconds
        self._cache: tuple[float, list[CpiInflationPoint]] | None = None
        self._client = httpx.AsyncClient(
            base_url=base_url or settings.mospi_base_url,
            timeout=timeout_seconds or settings.request_timeout_seconds,
            follow_redirects=True,
            headers={"Accept": "application/json,application/pdf", "User-Agent": settings.nse_user_agent},
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_combined_cpi_inflation(self, months: int = 6) -> list[CpiInflationPoint]:
        """Load a recent CPI series rather than leaving a new chart with one point."""

        if months < 2 or months > 12:
            raise ValueError("Inflation history must contain between 2 and 12 months.")
        if self._cache is not None:
            cached_at, points = self._cache
            if time.monotonic() - cached_at < self._cache_seconds:
                return points

        try:
            response = await self._client.post(MOSPI_RELEASES_PATH, json=_release_request_payload())
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise InflationSourceError(
                f"MoSPI CPI release feed returned HTTP {error.response.status_code}."
            ) from error
        except httpx.HTTPError as error:
            raise InflationSourceError("MoSPI CPI release feed request failed.") from error

        try:
            releases = parse_mospi_cpi_release_history(
                response.json(), str(self._client.base_url)
            )[:months]
        except ValueError as error:
            raise InflationSourceError("MoSPI CPI release feed returned invalid JSON.") from error

        points: list[CpiInflationPoint] = []
        for release in releases:
            try:
                pdf_response = await self._client.get(release.pdf_url)
                pdf_response.raise_for_status()
                points.append(parse_cpi_report_text(extract_pdf_text(pdf_response.content), release))
            except (InflationSourceError, httpx.HTTPError):
                # Historical files are occasionally replaced. Keep all other
                # validated releases rather than making the whole panel fail.
                continue

        if not points:
            raise InflationSourceError("MoSPI has no readable CPI releases.")
        history = sorted(points, key=lambda point: point.observation_date)
        self._cache = (time.monotonic(), history)
        return history


def parse_mospi_cpi_releases(payload: object, base_url: str) -> MospiCpiRelease:
    return parse_mospi_cpi_release_history(payload, base_url)[0]


def parse_mospi_cpi_release_history(payload: object, base_url: str) -> list[MospiCpiRelease]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise InflationSourceError("MoSPI CPI release feed has an invalid shape.")

    releases: list[MospiCpiRelease] = []
    for item in payload["data"]:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        published_value = item.get("published_year")
        file_one = item.get("file_one")
        if not isinstance(title, str) or not isinstance(published_value, str) or not isinstance(file_one, dict):
            continue
        period_match = _RELEASE_PERIOD_PATTERN.search(title)
        path = file_one.get("path")
        if period_match is None or not isinstance(path, str) or not path.lower().endswith(".pdf"):
            continue
        try:
            month = _month_number(period_match.group(1))
            year = int(period_match.group(2))
            published_date = date.fromisoformat(published_value)
        except ValueError as error:
            raise InflationSourceError("MoSPI CPI release has an invalid date.") from error
        releases.append(
            MospiCpiRelease(
                title=title,
                reference_period=date(year, month, 1),
                release_date=published_date,
                pdf_url=urljoin(base_url.rstrip("/") + "/", path),
                raw_payload=item,
            )
        )
    if not releases:
        raise InflationSourceError("MoSPI release feed has no CPI publication.")
    return sorted(releases, key=lambda release: release.reference_period, reverse=True)


def extract_pdf_text(pdf_content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(pdf_content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except (PdfReadError, OSError, ValueError) as error:
        raise InflationSourceError("MoSPI CPI release could not be read as a PDF.") from error
    if not text.strip():
        raise InflationSourceError("MoSPI CPI release contains no extractable text.")
    return text


def parse_cpi_report_text(report_text: str, release: MospiCpiRelease) -> CpiInflationPoint:
    match = _INFLATION_PATTERN.search(report_text)
    if match is None:
        raise InflationSourceError("MoSPI CPI release is missing the all-India CPI inflation rate.")
    observation_date = date(
        release.reference_period.year,
        release.reference_period.month,
        calendar.monthrange(release.reference_period.year, release.reference_period.month)[1],
    )
    if release.release_date < observation_date:
        raise InflationSourceError("MoSPI CPI release predates its reference period.")
    return CpiInflationPoint(
        period_label=f"{calendar.month_abbr[observation_date.month]} {observation_date.year}",
        observation_date=observation_date,
        source_as_of_date=release.release_date,
        inflation_percent=float(match.group(1)),
        raw_payload={
            "release_title": release.title,
            "release_date": release.release_date.isoformat(),
            "pdf_url": release.pdf_url,
            "all_india_combined_cpi_inflation_percent": float(match.group(1)),
            "rbi_target_percent": RBI_TARGET_PERCENT,
            "rbi_tolerance_band": RBI_TARGET_BAND,
            "rbi_target_source_url": RBI_TARGET_SOURCE_URL,
        },
    )


def _release_request_payload() -> dict[str, object]:
    return {
        "page_no": 1,
        "page_size": 50,
        "search_term": "",
        "sort_field": "published_year",
        "sort_order": "DESC",
        "from_date": "",
        "to_date": "",
        "lang": "en",
        "data_source": "web",
    }


def _month_number(value: str) -> int:
    normalized = value.strip().lower()[:3]
    for month in range(1, 13):
        if calendar.month_abbr[month].lower() == normalized:
            return month
    raise ValueError("month is invalid")
