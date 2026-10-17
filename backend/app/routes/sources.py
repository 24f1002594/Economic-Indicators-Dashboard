from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.db import Database, get_database
from app.schemas import ErrorResponse, SourceStatusResponse, UserResponse
from app.services.dashboard_service import list_sources


router = APIRouter(tags=["sources"])


@router.get(
    "/sources",
    response_model=list[SourceStatusResponse],
    responses={401: {"model": ErrorResponse}},
)
async def read_sources(
    _: UserResponse = Depends(get_current_user),
    database: Database = Depends(get_database),
) -> list[SourceStatusResponse]:
    return await list_sources(database)
