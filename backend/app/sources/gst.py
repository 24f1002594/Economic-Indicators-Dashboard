from __future__ import annotations

import calendar
import html
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


GST_SOURCE_KEY = "gst_portal_monthly_collection"
GST_NEWS_PATH = "/fomessage/newsupdates"
GST_INDICATOR_ID = "gst_collection_india"
GST_UNIT = "₹ lakh crore"
_RELEASE_PATTERN = re.compile(
    r"gross\s+and\s+net\s+gst\s+revenue\s+collections\s+for\s+the\s+month\s+of\s+"
    r"([A-Za-z]+),\s*(\d{4})",
    re.IGNORECASE,
)
_TOTAL_GROSS_PATTERN = re.compile(
    r"Total\s+Gross\s+GST\s+Revenue\s+([\d,]+)\s+([\d,]+)\s+[-\d.]+%",
    re.IGNORECASE,
)


class GstSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class GstNewsRelease:
    title: str
    period_month: int
    period_year: int
    published_date: date
    pdf_url: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class GstCollectionPoint:
    period_label: str
    observation_date: date
    source_as_of_date: date
    gross_collection_lakh_crore: float
    previous_year_collection_lakh_crore: float
    comparison_period_label: str
    raw_payload: dict[str, Any]


class GstClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
        cache_seconds: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self._cache_seconds = cache_seconds or settings.gst_cache_seconds
        self._cache: tuple[float, list[GstCollectionPoint]] | None = None
        self._client = httpx.AsyncClient(
            base_url=base_url or settings.gst_base_url,
            timeout=timeout_seconds or settings.request_timeout_seconds,
            follow_redirects=True,
            headers={"Accept": "application/json,application/pdf", "User-Agent": settings.nse_user_agent},
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_recent_collections(self, months: int = 6) -> list[GstCollectionPoint]:
        """Hydrate the chart from recent official releases on a new deployment."""

        if months < 2 or months > 12:
            raise ValueError("GST history must contain between 2 and 12 months.")
        if self._cache is not None:
            cached_at, points = self._cache
            if time.monotonic() - cached_at < self._cache_seconds:
                return points

        try:
            response = await self._client.get(GST_NEWS_PATH)
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise GstSourceError(
                f"GST Portal news feed returned HTTP {error.response.status_code}."
            ) from error
        except httpx.HTTPError as error:
            raise GstSourceError("GST Portal news feed request failed.") from error

        try:
            releases = parse_gst_news_releases(response.json(), str(self._client.base_url))[:months]
        except ValueError as error:
            raise GstSourceError("GST Portal news feed returned invalid JSON.") from error

        points: list[GstCollectionPoint] = []
        for release in releases:
            try:
                pdf_response = await self._client.get(release.pdf_url)
                pdf_response.raise_for_status()
                points.append(parse_gst_report_text(extract_pdf_text(pdf_response.content), release))
            except (GstSourceError, httpx.HTTPError):
                # A revised or removed historical attachment must not discard
                # the newest valid releases already obtained in this run.
                continue

        if not points:
            raise GstSourceError("GST Portal has no readable monthly collection releases.")
        history = sorted(points, key=lambda point: point.observation_date)
        self._cache = (time.monotonic(), history)
        return history

    async def fetch_latest_collection(self) -> GstCollectionPoint:
        """Compatibility helper for callers that require only the newest release."""

        return (await self.fetch_recent_collections(months=2))[-1]


def parse_gst_news_payload(payload: object, base_url: str) -> GstNewsRelease:
    return parse_gst_news_releases(payload, base_url)[0]


def parse_gst_news_releases(payload: object, base_url: str) -> list[GstNewsRelease]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise GstSourceError("GST Portal news feed has an invalid shape.")

    releases: list[GstNewsRelease] = []
    for item in payload["data"]:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        content = item.get("content")
        published_value = item.get("date")
        if not isinstance(title, str) or not isinstance(content, str) or not isinstance(published_value, str):
            continue
        title_match = _RELEASE_PATTERN.search(title)
        if title_match is None:
            continue
        pdf_match = re.search(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']', content, re.IGNORECASE)
        if pdf_match is None:
            raise GstSourceError("GST Portal monthly release is missing its PDF link.")
        try:
            month = _month_number(title_match.group(1))
            year = int(title_match.group(2))
            published_date = datetime.strptime(published_value, "%d/%m/%Y").date()
        except ValueError as error:
            raise GstSourceError("GST Portal monthly release contains an invalid date.") from error
        releases.append(
            GstNewsRelease(
                title=title,
                period_month=month,
                period_year=year,
                published_date=published_date,
                pdf_url=urljoin(base_url, html.unescape(pdf_match.group(1))),
                raw_payload=item,
            )
        )
    if not releases:
        raise GstSourceError("GST Portal news feed has no monthly collection release.")
    return sorted(
        releases,
        key=lambda release: (release.period_year, release.period_month),
        reverse=True,
    )


def extract_pdf_text(pdf_content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(pdf_content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except (PdfReadError, OSError, ValueError) as error:
        raise GstSourceError("GST Portal monthly report could not be read as a PDF.") from error
    if not text.strip():
        raise GstSourceError("GST Portal monthly report contains no extractable text.")
    return text


def parse_gst_report_text(report_text: str, release: GstNewsRelease) -> GstCollectionPoint:
    match = _TOTAL_GROSS_PATTERN.search(report_text)
    if match is None:
        raise GstSourceError("GST Portal monthly report is missing Total Gross GST Revenue.")
    previous_crore = _parse_crore(match.group(1))
    current_crore = _parse_crore(match.group(2))
    observation_date = date(
        release.period_year,
        release.period_month,
        calendar.monthrange(release.period_year, release.period_month)[1],
    )
    if release.published_date < observation_date:
        raise GstSourceError("GST Portal monthly release predates its reporting period.")
    period_label = f"{calendar.month_abbr[release.period_month]} {release.period_year}"
    comparison_period_label = f"{calendar.month_abbr[release.period_month]} {release.period_year - 1}"
    return GstCollectionPoint(
        period_label=period_label,
        observation_date=observation_date,
        source_as_of_date=release.published_date,
        gross_collection_lakh_crore=current_crore / 100_000,
        previous_year_collection_lakh_crore=previous_crore / 100_000,
        comparison_period_label=comparison_period_label,
        raw_payload={
            "release_title": release.title,
            "release_date": release.published_date.isoformat(),
            "pdf_url": release.pdf_url,
            "total_gross_gst_revenue_crore": current_crore,
            "previous_year_total_gross_gst_revenue_crore": previous_crore,
            "source_unit": "₹ crore",
        },
    )


def _month_number(value: str) -> int:
    normalized = value.strip().lower()[:3]
    for month in range(1, 13):
        if calendar.month_abbr[month].lower() == normalized:
            return month
    raise ValueError("month is invalid")


def _parse_crore(value: str) -> float:
    try:
        return float(value.replace(",", ""))
    except ValueError as error:
        raise GstSourceError("GST Portal monthly report has an invalid currency value.") from error
