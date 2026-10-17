from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from app.config import get_settings


DEBT_SOURCE_KEY = "world_bank_central_government_debt"
WORLD_BANK_DEBT_INDICATOR = "GC.DOD.TOTL.GD.ZS"
DEBT_COUNTRY_TO_INDICATOR = {
    "IND": ("debt_to_gdp_india", "Debt to GDP Ratio — India"),
    "USA": ("debt_to_gdp_us", "Debt to GDP Ratio — US"),
}
# Kept for callers that only ever cared about the India series.
DEBT_INDICATOR_ID = "debt_to_gdp_india"


class DebtSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class DebtToGdpPoint:
    indicator_id: str
    name: str
    year: int
    value: float
    source_as_of_date: date
    raw_payload: dict[str, Any]


class DebtClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
        cache_seconds: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self._cache_seconds = cache_seconds or settings.world_bank_cache_seconds
        self._cache: tuple[float, list[DebtToGdpPoint]] | None = None
        self._client = httpx.AsyncClient(
            base_url=base_url or settings.world_bank_base_url,
            timeout=timeout_seconds or settings.request_timeout_seconds,
            follow_redirects=True,
            headers={"Accept": "application/json"},
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_debt_to_gdp(self) -> list[DebtToGdpPoint]:
        if self._cache is not None:
            cached_at, points = self._cache
            if time.monotonic() - cached_at < self._cache_seconds:
                return points

        try:
            response = await self._client.get(
                f"/v2/country/IND;USA/indicator/{WORLD_BANK_DEBT_INDICATOR}",
                params={"format": "json", "per_page": 200},
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise DebtSourceError("World Bank debt-to-GDP request failed.") from error

        try:
            points = parse_debt_to_gdp_payload(response.json())
        except ValueError as error:
            raise DebtSourceError("World Bank returned a non-JSON debt-to-GDP response.") from error
        self._cache = (time.monotonic(), points)
        return points


def parse_debt_to_gdp_payload(payload: object) -> list[DebtToGdpPoint]:
    if not isinstance(payload, list) or len(payload) < 2:
        raise DebtSourceError("World Bank debt-to-GDP response has an invalid shape.")
    metadata, records = payload[0], payload[1]
    if not isinstance(metadata, dict) or not isinstance(records, list):
        raise DebtSourceError("World Bank debt-to-GDP response is missing metadata or records.")
    last_updated = metadata.get("lastupdated")
    if not isinstance(last_updated, str):
        raise DebtSourceError("World Bank debt-to-GDP response is missing its last-updated date.")
    try:
        source_as_of_date = date.fromisoformat(last_updated)
    except ValueError as error:
        raise DebtSourceError("World Bank debt-to-GDP last-updated date is invalid.") from error

    points_by_indicator: dict[str, list[DebtToGdpPoint]] = {
        indicator_id: [] for indicator_id, _ in DEBT_COUNTRY_TO_INDICATOR.values()
    }
    for record in records:
        if not isinstance(record, dict):
            continue
        country_code = record.get("countryiso3code")
        if country_code not in DEBT_COUNTRY_TO_INDICATOR or record.get("value") is None:
            continue
        indicator_id, name = DEBT_COUNTRY_TO_INDICATOR[country_code]
        try:
            year = int(str(record["date"]))
            value = float(record["value"])
        except (KeyError, TypeError, ValueError) as error:
            raise DebtSourceError("World Bank debt-to-GDP record contains an invalid value.") from error
        points_by_indicator[indicator_id].append(
            DebtToGdpPoint(
                indicator_id=indicator_id,
                name=name,
                year=year,
                value=value,
                source_as_of_date=source_as_of_date,
                raw_payload=record,
            )
        )

    missing = [indicator_id for indicator_id, points in points_by_indicator.items() if not points]
    if missing:
        raise DebtSourceError(
            "World Bank debt-to-GDP response is missing observations for: " + ", ".join(missing)
        )

    return [
        point
        for points in points_by_indicator.values()
        for point in sorted(points, key=lambda point: point.year)[-6:]
    ]
