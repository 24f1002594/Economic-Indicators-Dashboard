from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
# APIRouter — Organizes API endpoints.
# Depends — Provides required dependencies, such as the database manager.
# HTTPException and status — Return appropriate HTTP errors when something fails.
from app.config import get_settings
from app.db import Database, get_database
from app.schemas import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(database: Database = Depends(get_database)) -> HealthResponse:
    try:
        database_is_available = await database.ping()
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from error

    if not database_is_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        )

    settings = get_settings()
    return HealthResponse(
        status="ok",
        database="ok",
        environment=settings.app_env,
        version="0.1.0",
        timestamp=datetime.now(timezone.utc),
    )
