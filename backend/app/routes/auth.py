from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.auth import authenticate_user, create_access_token, credentials_exception, get_current_user
from app.db import Database, get_database
from app.rate_limit import limiter
from app.schemas import ErrorResponse, LoginRequest, TokenResponse, UserResponse


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
)
@limiter.limit("10/minute")
async def login(
    request: Request,
    credentials: LoginRequest,
    database: Database = Depends(get_database),
) -> TokenResponse:
    user = await authenticate_user(credentials.email, credentials.password, database)
    if user is None:
        raise credentials_exception()

    token, expires_in = create_access_token(user)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get(
    "/me",
    response_model=UserResponse,
    responses={401: {"model": ErrorResponse}},
)
async def read_current_user(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    return current_user
