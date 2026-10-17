from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.db import Database, get_database
from app.schemas import DashboardResponse, ErrorResponse, UserResponse
from app.services.dashboard_service import build_dashboard


router = APIRouter(tags=["dashboard"])


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    responses={401: {"model": ErrorResponse}},
)
async def read_dashboard(
    _: UserResponse = Depends(get_current_user),
    database: Database = Depends(get_database),
) -> DashboardResponse:
    return await build_dashboard(database)
