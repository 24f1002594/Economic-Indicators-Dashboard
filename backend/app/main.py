from __future__ import annotations # Helps Python handle type hints.

from collections.abc import AsyncIterator # Allows you to work with asynchronous iterators
from contextlib import asynccontextmanager # Provides a way to create asynchronous context managers

from fastapi import FastAPI # FastAPI creates your backend application.
from fastapi.middleware.cors import CORSMiddleware # CORSMiddleware controls which frontend websites can access your API.
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings # loads your application configuration.
from app.db import database # manages PostgreSQL connections.
from app.rate_limit import limiter
from app.routes.auth import router as auth_router
from app.routes.dashboard import router as dashboard_router
from app.routes.health import router as health_router # provides the API’s health-check endpoint.
from app.routes.indicators import router as indicators_router
from app.routes.sources import router as sources_router
from app.scheduler import start_collector_scheduler, stop_collector_scheduler
from app.services.collector_service import initialize_dashboard_metadata


settings = get_settings()
# loads your application configuration.

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await database.open() # Opens the database connection pool
    await initialize_dashboard_metadata(database)
    await start_collector_scheduler(database)
    try:
        yield # Allows the application to run and handle requests
    finally:
        stop_collector_scheduler()
        await database.close() # Closes the database connection pool.


app = FastAPI(
    title="Economic Indicators Dashboard API",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health_router)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(dashboard_router, prefix=settings.api_prefix)
app.include_router(indicators_router, prefix=settings.api_prefix)
app.include_router(sources_router, prefix=settings.api_prefix)
