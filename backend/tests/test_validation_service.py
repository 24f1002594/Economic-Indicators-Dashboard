from datetime import date, timedelta

from app.services.validation_service import observation_key, validate_payload


def valid_payload() -> dict[str, object]:
    return {
        "indicator_id": "gdp_growth_india",
        "source_key": "development_fixture",
        "period_label": "FY 2025-26",
        "observation_date": date(2026, 3, 31),
        "source_as_of_date": date.today(),
        "value": 6.8,
        "unit": "%",
        "comparison_value": 6.5,
        "comparison_period_label": "FY 2024-25",
        "raw_payload": {"value": 6.8},
    }


def test_valid_observation_passes_validation() -> None:
    result = validate_payload(valid_payload())

    assert result.is_valid
    assert result.observation is not None
    assert observation_key(result.observation) == (
        "gdp_growth_india",
        "development_fixture",
        "FY 2025-26",
        date.today(),
    )


def test_invalid_unit_is_rejected() -> None:
    payload = valid_payload()
    payload["unit"] = "USD"

    result = validate_payload(payload)

    assert not result.is_valid
    assert "does not match expected unit" in result.errors[0]


def test_out_of_range_value_is_rejected() -> None:
    payload = valid_payload()
    payload["value"] = 200

    result = validate_payload(payload)

    assert not result.is_valid
    assert "outside the accepted range" in result.errors[0]


def test_future_source_date_is_rejected() -> None:
    payload = valid_payload()
    payload["source_as_of_date"] = date.today() + timedelta(days=1)

    result = validate_payload(payload)

    assert not result.is_valid
    assert any("cannot be in the future" in error for error in result.errors)


def test_comparison_period_requires_value() -> None:
    payload = valid_payload()
    payload["comparison_value"] = None

    result = validate_payload(payload)

    assert not result.is_valid
    assert "Comparison period requires a comparison value." in result.errors
