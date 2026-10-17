from datetime import date

import pytest

from app.sources.world_bank import WorldBankSourceError, parse_gdp_growth_payload


def world_bank_payload() -> list[object]:
    return [
        {"lastupdated": "2026-10-16"},
        [
            {"countryiso3code": "IND", "date": "2025", "value": 6.5},
            {"countryiso3code": "IND", "date": "2024", "value": 7.2},
            {"countryiso3code": "WLD", "date": "2025", "value": 2.8},
            {"countryiso3code": "WLD", "date": "2024", "value": 3.1},
        ],
    ]


def test_parse_gdp_growth_payload_returns_india_and_world_points() -> None:
    points = parse_gdp_growth_payload(world_bank_payload())

    assert len(points) == 4
    assert {point.indicator_id for point in points} == {
        "gdp_growth_india",
        "gdp_growth_world",
    }
    assert points[0].source_as_of_date == date(2026, 10, 16)


def test_parse_gdp_growth_payload_rejects_missing_world_data() -> None:
    payload = world_bank_payload()
    payload[1] = payload[1][:2]

    with pytest.raises(WorldBankSourceError, match="gdp_growth_world"):
        parse_gdp_growth_payload(payload)
