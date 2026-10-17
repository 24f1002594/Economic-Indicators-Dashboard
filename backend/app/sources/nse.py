from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx

from app.config import get_settings


NSE_SOURCE_KEY = "nse_indices"
NSE_ALL_INDICES_PATH = "/api/allIndices"
TRACKED_INDICES = {
    "NIFTY 50": ("nifty_50", "NIFTY 50"),
    "NIFTY BANK": ("nifty_bank", "NIFTY BANK"),
    "NIFTY IT": ("nifty_it", "NIFTY IT"),
}


class NseSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class NseIndexQuote:
    indicator_id: str
    name: str
    last_price: float
    change: float | None
    change_percent: float | None
    as_of_date: date
    raw_payload: dict[str, Any]


class NseClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
        cache_seconds: int | None = None,
        user_agent: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self._cache_seconds = cache_seconds or settings.nse_cache_seconds
        self._cache: tuple[float, list[NseIndexQuote]] | None = None
        self._client = httpx.AsyncClient(
            base_url=base_url or settings.nse_base_url,
            timeout=timeout_seconds or settings.request_timeout_seconds,
            follow_redirects=True,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-IN,en;q=0.9",
                "User-Agent": user_agent or settings.nse_user_agent,
            },
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_quotes(self) -> list[NseIndexQuote]:
        if self._cache is not None:
            cached_at, cached_quotes = self._cache
            if time.monotonic() - cached_at < self._cache_seconds:
                return cached_quotes

        try:
            bootstrap_response = await self._client.get("/")
            bootstrap_response.raise_for_status()
            response = await self._client.get(NSE_ALL_INDICES_PATH)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise NseSourceError("NSE index request failed.") from error

        try:
            payload = response.json()
        except ValueError as error:
            raise NseSourceError("NSE returned a non-JSON index response.") from error

        quotes = parse_all_indices_payload(payload)
        self._cache = (time.monotonic(), quotes)
        return quotes


def parse_all_indices_payload(payload: object) -> list[NseIndexQuote]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise NseSourceError("NSE index response does not contain a data list.")

    response_timestamp = payload.get("timestamp")

    records_by_name = {
        record.get("index"): record
        for record in payload["data"]
        if isinstance(record, dict) and isinstance(record.get("index"), str)
    }
    missing_indices = [name for name in TRACKED_INDICES if name not in records_by_name]
    if missing_indices:
        raise NseSourceError(f"NSE response is missing: {', '.join(missing_indices)}.")

    quotes: list[NseIndexQuote] = []
    for nse_name, (indicator_id, display_name) in TRACKED_INDICES.items():
        record = records_by_name[nse_name]
        quotes.append(
            NseIndexQuote(
                indicator_id=indicator_id,
                name=display_name,
                last_price=_as_number(record.get("last"), "last", nse_name),
                change=_as_optional_number(record.get("variation"), "variation", nse_name),
                change_percent=_as_optional_number(
                    record.get("percentChange"), "percentChange", nse_name
                ),
                as_of_date=_as_source_date(record, response_timestamp),
                raw_payload=record,
            )
        )
    return quotes


def _as_number(value: object, field_name: str, index_name: str) -> float:
    parsed = _as_optional_number(value, field_name, index_name)
    if parsed is None:
        raise NseSourceError(f"NSE {index_name} is missing {field_name}.")
    return parsed


def _as_optional_number(value: object, field_name: str, index_name: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError) as error:
        raise NseSourceError(
            f"NSE {index_name} has an invalid {field_name} value."
        ) from error


def _as_source_date(record: dict[str, Any], response_timestamp: object) -> date:
    if isinstance(response_timestamp, str) and response_timestamp.strip():
        parsed = _parse_nse_date(response_timestamp.strip())
        if parsed is not None:
            return parsed
    for field_name in ("timeVal", "lastUpdateTime", "timestamp"):
        value = record.get(field_name)
        if not isinstance(value, str) or not value.strip():
            continue
        parsed = _parse_nse_date(value.strip())
        if parsed is not None:
            return parsed
    raise NseSourceError("NSE index response is missing a readable source timestamp.")


def _parse_nse_date(value: str) -> date | None:
    for date_format in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%b-%Y"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
