from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum # Defines a set of allowed string values
from typing import Literal # Restricts a field to specific values.

from pydantic import BaseModel, ConfigDict, Field

class FreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    MISSING = "missing"


class UserRole(StrEnum):
    VIEWER = "viewer"
    ADMIN = "admin"


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(ge=1)


class UserResponse(BaseModel):
    id: int = Field(gt=0)
    email: str = Field(max_length=320)
    role: UserRole
    is_active: bool
    created_at: datetime


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["ok"]
    environment: Literal["development", "test", "production"]
    version: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    detail: str


class IndicatorResponse(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=64)
    description: str | None = None
    is_active: bool


class SourceResponse(BaseModel):
    source_key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=1)
    refresh_interval_minutes: int = Field(ge=5)
    limitation: str | None = None


class SourceStatusResponse(SourceResponse):
    status: FreshnessStatus
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    stale_after_at: datetime | None = None


class ObservationResponse(BaseModel):
    indicator_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=100)
    period_label: str = Field(min_length=1, max_length=100)
    observation_date: date
    source_as_of_date: date
    value: float
    unit: str = Field(min_length=1, max_length=64)
    comparison_value: float | None = None
    comparison_period_label: str | None = Field(default=None, max_length=100)
    collected_at: datetime


class IndicatorHistoryPoint(BaseModel):
    period_label: str = Field(min_length=1, max_length=100)
    observation_date: date
    value: float


class DashboardIndicatorResponse(BaseModel):
    indicator: IndicatorResponse
    value: float | None = None
    period_label: str | None = Field(default=None, max_length=100)
    comparison_value: float | None = None
    comparison_period_label: str | None = Field(default=None, max_length=100)
    change: float | None = None
    change_percent: float | None = None
    as_of_date: date | None = None
    freshness_status: FreshnessStatus
    source: SourceStatusResponse
    history: list[IndicatorHistoryPoint]
    message: str | None = None


class MarketTickerItem(BaseModel):
    symbol: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    last_price: float | None = None
    change: float | None = None
    change_percent: float | None = None
    as_of: datetime | None = None
    freshness_status: FreshnessStatus
    source: SourceStatusResponse


class DashboardResponse(BaseModel):
    generated_at: datetime
    ticker: list[MarketTickerItem]
    indicators: list[DashboardIndicatorResponse]


class CollectionRunResponse(BaseModel):
    id: int = Field(gt=0)
    source_key: str = Field(min_length=1, max_length=100)
    status: Literal["running", "succeeded", "failed"]
    started_at: datetime
    completed_at: datetime | None = None
    records_received: int = Field(ge=0)
    records_stored: int = Field(ge=0)
    error_message: str | None = None
