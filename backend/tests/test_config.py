import pytest
from pydantic import ValidationError

from app.config import Settings


def settings_values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "database_url": "postgresql://dashboard:password@localhost:5432/economic_dashboard",
        "jwt_secret_key": "a" * 32,
        "cors_origins": "https://dashboard.example.com",
    }
    values.update(overrides)
    return values


def test_production_requires_an_https_cors_origin() -> None:
    with pytest.raises(ValidationError, match="must use HTTPS"):
        Settings(**settings_values(app_env="production", cors_origins="http://localhost:5173"))


def test_cors_wildcards_are_rejected() -> None:
    with pytest.raises(ValidationError, match="must not contain a wildcard"):
        Settings(**settings_values(cors_origins="*"))
