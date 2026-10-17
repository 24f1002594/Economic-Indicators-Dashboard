from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from app.db import Database, get_database
from app.schemas import ErrorResponse, IndicatorResponse, ObservationResponse, UserResponse
from app.services.dashboard_service import get_indicator, list_indicator_history, list_indicators


router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.get("", response_model=list[IndicatorResponse], responses={401: {"model": ErrorResponse}})
async def read_indicators(
    _: UserResponse = Depends(get_current_user),
    database: Database = Depends(get_database),
) -> list[IndicatorResponse]:
    return await list_indicators(database)


@router.get(
    "/{indicator_id}",
    response_model=IndicatorResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def read_indicator(
    indicator_id: str,
    _: UserResponse = Depends(get_current_user),
    database: Database = Depends(get_database),
) -> IndicatorResponse:
    indicator = await get_indicator(indicator_id, database)
    if indicator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Indicator was not found.")
    return indicator


@router.get(
    "/{indicator_id}/history",
    response_model=list[ObservationResponse],
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def read_indicator_history(
    indicator_id: str,
    _: UserResponse = Depends(get_current_user),
    database: Database = Depends(get_database),
) -> list[ObservationResponse]:
    indicator = await get_indicator(indicator_id, database)
    if indicator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Indicator was not found.")
    return await list_indicator_history(indicator_id, database)
