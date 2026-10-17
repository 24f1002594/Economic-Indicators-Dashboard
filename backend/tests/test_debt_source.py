from datetime import date

import pytest

from app.sources.debt import DebtSourceError, parse_debt_to_gdp_payload


def debt_payload() -> list[object]:
    return [
        {"lastupdated": "2026-10-08"},
        [
            {"countryiso3code": "IND", "date": "2025", "value": None},
            {"countryiso3code": "IND", "date": "2018", "value": 46.5224986659322},
            {"countryiso3code": "IND", "date": "2017", "value": 47.5836093800197},
            {"countryiso3code": "USA", "date": "2024", "value": 115.788609964778},
            {"countryiso3code": "USA", "date": "2023", "value": 114.73985759209},
        ],
    ]


def test_parse_debt_to_gdp_payload_returns_india_and_us_points() -> None:
    points = parse_debt_to_gdp_payload(debt_payload())

    assert len(points) == 4
    assert {point.indicator_id for point in points} == {
        "debt_to_gdp_india",
        "debt_to_gdp_us",
    }
    india_points = [point for point in points if point.indicator_id == "debt_to_gdp_india"]
    assert [point.year for point in india_points] == [2017, 2018]
    assert india_points[-1].value == pytest.approx(46.5224986659322)
    assert india_points[-1].source_as_of_date == date(2026, 10, 8)

    us_points = [point for point in points if point.indicator_id == "debt_to_gdp_us"]
    assert [point.year for point in us_points] == [2023, 2024]
    assert us_points[-1].value == pytest.approx(115.788609964778)


def test_parse_debt_to_gdp_payload_rejects_missing_us_data() -> None:
    payload = debt_payload()
    payload[1] = payload[1][:3]

    with pytest.raises(DebtSourceError, match="debt_to_gdp_us"):
        parse_debt_to_gdp_payload(payload)
