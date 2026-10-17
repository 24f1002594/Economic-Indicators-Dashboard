from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api/v1"

    database_url: PostgresDsn

    jwt_secret_key: SecretStr = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=1, le=1_440)

    cors_origins: str = "http://localhost:5173"

    collector_enabled: bool = False
    collector_interval_minutes: int = Field(default=60, ge=5)
    collector_run_on_startup: bool = True
    nse_base_url: str = "https://www.nseindia.com"
    nse_cache_seconds: int = Field(default=300, ge=60)
    nse_user_agent: str = Field(
        default="EconomicIndicatorsDashboard/0.1 (development collector)", min_length=1
    )
    world_bank_base_url: str = "https://api.worldbank.org"
    world_bank_cache_seconds: int = Field(default=21_600, ge=300)
    trade_base_url: str = "https://tradestat.commerce.gov.in"
    trade_cache_seconds: int = Field(default=21_600, ge=300)
    trade_refresh_hours: int = Field(default=24, ge=1, le=168)
    gst_base_url: str = "https://www.gst.gov.in"
    gst_cache_seconds: int = Field(default=21_600, ge=300)
    gst_refresh_hours: int = Field(default=24, ge=1, le=168)
    mospi_base_url: str = "https://www.mospi.gov.in"
    mospi_cpi_cache_seconds: int = Field(default=21_600, ge=300)
    inflation_refresh_hours: int = Field(default=24, ge=1, le=168)
    expenditure_base_url: str = "https://www.indiabudget.gov.in"
    expenditure_cache_seconds: int = Field(default=86_400, ge=300)
    expenditure_refresh_hours: int = Field(default=168, ge=24, le=8_760)
    request_timeout_seconds: int = Field(default=15, ge=1, le=120)

    @model_validator(mode="after")
    def validate_cors_origins(self) -> "Settings":
        origins = self.allowed_cors_origins
        if not origins:
            raise ValueError("CORS_ORIGINS must include at least one frontend origin.")
        if "*" in origins:
            raise ValueError("CORS_ORIGINS must not contain a wildcard origin.")
        if self.app_env == "production" and any(not origin.startswith("https://") for origin in origins):
            raise ValueError("Production CORS_ORIGINS entries must use HTTPS.")
        return self

    @property
    def allowed_cors_origins(self) -> list[str]:
        """Return a clean list from the comma-separated CORS_ORIGINS value."""

        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Create settings once per process and fail early on invalid configuration."""

    return Settings()
