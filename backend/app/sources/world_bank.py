from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from app.config import get_settings


WORLD_BANK_SOURCE_KEY = "world_bank_gdp"
WORLD_BANK_GDP_GROWTH_INDICATOR = "NY.GDP.MKTP.KD.ZG"
COUNTRY_TO_INDICATOR = {
    "IND": ("gdp_growth_india", "GDP Growth — India"),
    "WLD": ("gdp_growth_world", "GDP Growth — World"),
}


class WorldBankSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorldBankGrowthPoint:
    indicator_id: str
    name: str
    year: int
    value: float
    source_as_of_date: date
    raw_payload: dict[str, Any]


class WorldBankClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
        cache_seconds: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self._cache_seconds = cache_seconds or settings.world_bank_cache_seconds
        self._cache: tuple[float, list[WorldBankGrowthPoint]] | None = None
        self._client = httpx.AsyncClient(
            base_url=base_url or settings.world_bank_base_url,
            timeout=timeout_seconds or settings.request_timeout_seconds,
            follow_redirects=True,
            headers={"Accept": "application/json"},
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_gdp_growth(self) -> list[WorldBankGrowthPoint]:
        if self._cache is not None:
            cached_at, points = self._cache
            if time.monotonic() - cached_at < self._cache_seconds:
                return points

        try:
            response = await self._client.get(
                f"/v2/country/IND;WLD/indicator/{WORLD_BANK_GDP_GROWTH_INDICATOR}",
                params={"format": "json", "per_page": 100},
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise WorldBankSourceError("World Bank GDP request failed.") from error

        try:
            payload = response.json()
        except ValueError as error:
            raise WorldBankSourceError("World Bank returned a non-JSON GDP response.") from error

        points = parse_gdp_growth_payload(payload)
        self._cache = (time.monotonic(), points)
        return points


def parse_gdp_growth_payload(payload: object) -> list[WorldBankGrowthPoint]:
    if not isinstance(payload, list) or len(payload) < 2:
        raise WorldBankSourceError("World Bank GDP response has an invalid shape.")
    metadata, records = payload[0], payload[1]
    if not isinstance(metadata, dict) or not isinstance(records, list):
        raise WorldBankSourceError("World Bank GDP response is missing metadata or records.")

    source_as_of_date = _parse_source_as_of_date(metadata.get("lastupdated"))
    points_by_indicator: dict[str, list[WorldBankGrowthPoint]] = {
        indicator_id: [] for indicator_id, _ in COUNTRY_TO_INDICATOR.values()
    }
    for record in records:
        if not isinstance(record, dict):
            continue
        country_code = record.get("countryiso3code")
        if country_code not in COUNTRY_TO_INDICATOR or record.get("value") is None:
            continue
        indicator_id, name = COUNTRY_TO_INDICATOR[country_code]
        try:
            year = int(str(record["date"]))
            value = float(record["value"])
        except (KeyError, TypeError, ValueError) as error:
            raise WorldBankSourceError("World Bank GDP record contains an invalid value.") from error
        points_by_indicator[indicator_id].append(
            WorldBankGrowthPoint(
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
        raise WorldBankSourceError(
            "World Bank GDP response is missing observations for: " + ", ".join(missing)
        )

    return [
        point
        for points in points_by_indicator.values()
        for point in sorted(points, key=lambda point: point.year)[-6:]
    ]


def _parse_source_as_of_date(value: object) -> date:
    if not isinstance(value, str):
        raise WorldBankSourceError("World Bank GDP response is missing its last-updated date.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise WorldBankSourceError("World Bank GDP last-updated date is invalid.") from error
