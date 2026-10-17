from __future__ import annotations

import io
import re
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import get_settings


EXPENDITURE_SOURCE_KEY = "union_budget_expenditure"
BUDGET_AT_A_GLANCE_PATH = "/doc/Budget_at_Glance/bag1.pdf"
TOTAL_EXPENDITURE_INDICATOR_ID = "government_expenditure_india"
CAPITAL_EXPENDITURE_INDICATOR_ID = "government_capital_expenditure_india"
EXPENDITURE_UNIT = "₹ lakh crore"
_BUDGET_YEAR_PATTERN = re.compile(r"Budget\s+at\s+a\s+Glance\s+(\d{4})\s*-\s*(\d{2,4})", re.IGNORECASE)
_BUDGET_FIGURES_PATTERN = re.compile(
    r"total\s+expenditure\s+in\s+Budget\s+Estimates\s*\(BE\)\s*"
    r"(\d{4})\s*-\s*(\d{2,4})\s+is\s+estimated\s+at\s+₹\s*([\d,]+)\s+crore\s+"
    r"of\s+which\s+total\s+capital\s+expenditure\s+is\s+₹\s*([\d,]+)\s+crore",
    re.IGNORECASE,
)
_REVISED_FIGURES_PATTERN = re.compile(
    r"In\s+Revised\s+Estimates\s*\(RE\)\s*(\d{4})\s*-\s*(\d{2,4})\s*,\s*"
    r"the\s+total\s+expenditure\s+is\s+estimated\s+at\s+₹\s*([\d,]+)\s+crore.*?"
    r"total\s+capital\s+expenditure\s+is\s+estimated\s+at\s+₹\s*([\d,]+)\s+crore",
    re.IGNORECASE | re.DOTALL,
)
class ExpenditureSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExpenditurePoint:
    indicator_id: str
    period_label: str
    observation_date: date
    source_as_of_date: date
    value_lakh_crore: float
    comparison_value_lakh_crore: float
    comparison_period_label: str
    raw_payload: dict[str, Any]


class ExpenditureClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
        cache_seconds: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self._cache_seconds = cache_seconds or settings.expenditure_cache_seconds
        self._cache: tuple[float, list[ExpenditurePoint]] | None = None
        self._client = httpx.AsyncClient(
            base_url=base_url or settings.expenditure_base_url,
            timeout=timeout_seconds or settings.request_timeout_seconds,
            follow_redirects=True,
            headers={"Accept": "application/pdf", "User-Agent": settings.nse_user_agent},
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_latest_expenditure(self) -> list[ExpenditurePoint]:
        if self._cache is not None:
            cached_at, points = self._cache
            if time.monotonic() - cached_at < self._cache_seconds:
                return points

        try:
            response = await self._client.get(BUDGET_AT_A_GLANCE_PATH)
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise ExpenditureSourceError(
                f"Union Budget report returned HTTP {error.response.status_code}."
            ) from error
        except httpx.HTTPError as error:
            raise ExpenditureSourceError("Union Budget report request failed.") from error

        text, source_as_of_date = extract_budget_pdf(response.content)
        points = parse_budget_at_a_glance_text(text, source_as_of_date)
        self._cache = (time.monotonic(), points)
        return points


def extract_budget_pdf(pdf_content: bytes) -> tuple[str, date]:
    try:
        reader = PdfReader(io.BytesIO(pdf_content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        creation_date = reader.metadata.creation_date
    except (PdfReadError, OSError, ValueError) as error:
        raise ExpenditureSourceError("Union Budget report could not be read as a PDF.") from error

    if not text.strip():
        raise ExpenditureSourceError("Union Budget report contains no extractable text.")
    if creation_date is None:
        raise ExpenditureSourceError("Union Budget report is missing its publication date.")
    return text, creation_date.date()


def parse_budget_at_a_glance_text(report_text: str, source_as_of_date: date) -> list[ExpenditurePoint]:
    normalized_text = " ".join(report_text.split())
    budget_match = _BUDGET_YEAR_PATTERN.search(normalized_text)
    figures_match = _BUDGET_FIGURES_PATTERN.search(normalized_text)
    revised_match = _REVISED_FIGURES_PATTERN.search(normalized_text)
    if budget_match is None or figures_match is None or revised_match is None:
        raise ExpenditureSourceError("Union Budget report is missing the expected expenditure figures.")

    budget_period = _financial_year_label(figures_match.group(1), figures_match.group(2))
    revised_period = _financial_year_label(revised_match.group(1), revised_match.group(2))
    document_period = _financial_year_label(budget_match.group(1), budget_match.group(2))
    if budget_period != document_period:
        raise ExpenditureSourceError("Union Budget report has inconsistent budget years.")

    total_crore = _parse_crore(figures_match.group(3))
    capital_crore = _parse_crore(figures_match.group(4))
    revised_total_crore = _parse_crore(revised_match.group(3))
    revised_capital_crore = _parse_crore(revised_match.group(4))
    raw_payload = {
        "document": "Budget at a Glance",
        "budget_estimate_period": budget_period,
        "revised_estimate_period": revised_period,
        "source_as_of_date": source_as_of_date.isoformat(),
        "source_unit": "₹ crore",
        "total_expenditure_crore": total_crore,
        "capital_expenditure_crore": capital_crore,
        "revised_total_expenditure_crore": revised_total_crore,
        "revised_capital_expenditure_crore": revised_capital_crore,
    }
    return [
        ExpenditurePoint(
            indicator_id=TOTAL_EXPENDITURE_INDICATOR_ID,
            period_label=f"BE {budget_period}",
            observation_date=source_as_of_date,
            source_as_of_date=source_as_of_date,
            value_lakh_crore=total_crore / 100_000,
            comparison_value_lakh_crore=revised_total_crore / 100_000,
            comparison_period_label=f"RE {revised_period}",
            raw_payload={**raw_payload, "measure": "total_expenditure"},
        ),
        ExpenditurePoint(
            indicator_id=CAPITAL_EXPENDITURE_INDICATOR_ID,
            period_label=f"BE {budget_period}",
            observation_date=source_as_of_date,
            source_as_of_date=source_as_of_date,
            value_lakh_crore=capital_crore / 100_000,
            comparison_value_lakh_crore=revised_capital_crore / 100_000,
            comparison_period_label=f"RE {revised_period}",
            raw_payload={**raw_payload, "measure": "capital_expenditure"},
        ),
    ]


def _financial_year_label(start_year: str, end_year: str) -> str:
    normalized_end_year = end_year[-2:]
    return f"FY {start_year}-{normalized_end_year}"


def _parse_crore(value: str) -> float:
    try:
        return float(value.replace(",", ""))
    except ValueError as error:
        raise ExpenditureSourceError("Union Budget report has an invalid currency value.") from error
