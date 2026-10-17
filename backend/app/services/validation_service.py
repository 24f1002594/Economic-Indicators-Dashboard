from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError


IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True)
class IndicatorRule:
    unit: str
    minimum: float
    maximum: float


INDICATOR_RULES: dict[str, IndicatorRule] = {
    "gdp_growth_india": IndicatorRule(unit="%", minimum=-50, maximum=50),
    "gdp_growth_world": IndicatorRule(unit="%", minimum=-50, maximum=50),
    "debt_to_gdp_india": IndicatorRule(unit="%", minimum=0, maximum=300),
    "debt_to_gdp_us": IndicatorRule(unit="%", minimum=0, maximum=300),
    "exports_india": IndicatorRule(unit="USD billion", minimum=0, maximum=10_000),
    "imports_india": IndicatorRule(unit="USD billion", minimum=0, maximum=10_000),
    "trade_balance_india": IndicatorRule(unit="USD billion", minimum=-10_000, maximum=10_000),
    "gst_collection_india": IndicatorRule(unit="₹ lakh crore", minimum=0, maximum=50),
    "inflation_india": IndicatorRule(unit="%", minimum=-20, maximum=100),
    "government_expenditure_india": IndicatorRule(
        unit="₹ lakh crore", minimum=0, maximum=500
    ),
    "government_capital_expenditure_india": IndicatorRule(
        unit="₹ lakh crore", minimum=0, maximum=500
    ),
    "nifty_50": IndicatorRule(unit="points", minimum=0, maximum=1_000_000),
    "sensex": IndicatorRule(unit="points", minimum=0, maximum=1_000_000),
    "nifty_bank": IndicatorRule(unit="points", minimum=0, maximum=1_000_000),
    "nifty_it": IndicatorRule(unit="points", minimum=0, maximum=1_000_000),
}


class ObservationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    indicator_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=100)
    period_label: str = Field(min_length=1, max_length=100)
    observation_date: date
    source_as_of_date: date
    value: float
    unit: str = Field(min_length=1, max_length=64)
    comparison_value: float | None = None
    comparison_period_label: str | None = Field(default=None, max_length=100)
    raw_payload: Any | None = None


@dataclass(frozen=True)
class ObservationValidationResult:
    observation: ObservationCandidate | None
    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return self.observation is not None and not self.errors


def validate_payload(payload: Mapping[str, Any]) -> ObservationValidationResult:
    try:
        observation = ObservationCandidate.model_validate(payload)
    except ValidationError as error:
        errors = tuple(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors()
        )
        return ObservationValidationResult(observation=None, errors=errors)

    return validate_observation(observation)


def validate_observation(observation: ObservationCandidate) -> ObservationValidationResult:
    errors: list[str] = []
    rule = INDICATOR_RULES.get(observation.indicator_id)

    if rule is None:
        errors.append(f"Unknown indicator '{observation.indicator_id}'.")
    elif observation.unit != rule.unit:
        errors.append(
            f"Unit '{observation.unit}' does not match expected unit '{rule.unit}'."
        )
    elif observation.value < rule.minimum or observation.value > rule.maximum:
        errors.append(
            f"Value {observation.value} is outside the accepted range "
            f"{rule.minimum} to {rule.maximum}."
        )

    if not IDENTIFIER_PATTERN.fullmatch(observation.indicator_id):
        errors.append("Indicator ID may contain only lowercase letters, numbers, and underscores.")
    if not IDENTIFIER_PATTERN.fullmatch(observation.source_key):
        errors.append("Source key may contain only lowercase letters, numbers, and underscores.")
    if not math.isfinite(observation.value):
        errors.append("Value must be a finite number.")
    if observation.comparison_value is not None and not math.isfinite(observation.comparison_value):
        errors.append("Comparison value must be a finite number.")
    if observation.observation_date > observation.source_as_of_date:
        errors.append("Observation date cannot be later than the source as-of date.")
    if observation.source_as_of_date > date.today():
        errors.append("Source as-of date cannot be in the future.")
    if observation.comparison_value is None and observation.comparison_period_label is not None:
        errors.append("Comparison period requires a comparison value.")
    if observation.comparison_value is not None and not observation.comparison_period_label:
        errors.append("Comparison value requires a comparison period label.")
    if observation.comparison_period_label == observation.period_label:
        errors.append("Comparison period cannot match the current period.")
    if observation.raw_payload is not None:
        try:
            json.dumps(observation.raw_payload)
        except (TypeError, ValueError):
            errors.append("Raw payload must be JSON serializable.")

    if errors:
        return ObservationValidationResult(observation=None, errors=tuple(errors))
    return ObservationValidationResult(observation=observation, errors=())


def observation_key(observation: ObservationCandidate) -> tuple[str, str, str, date]:
    return (
        observation.indicator_id,
        observation.source_key,
        observation.period_label,
        observation.source_as_of_date,
    )
