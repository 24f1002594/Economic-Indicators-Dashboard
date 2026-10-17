from __future__ import annotations

from datetime import datetime, timezone

from app.db import Database
from app.schemas import (
    DashboardIndicatorResponse,
    DashboardResponse,
    IndicatorHistoryPoint,
    IndicatorResponse,
    MarketTickerItem,
    ObservationResponse,
    SourceStatusResponse,
)


async def list_indicators(database: Database) -> list[IndicatorResponse]:
    rows = await database.fetch_all(
        """
        SELECT id, name, category, unit, description, is_active
        FROM indicators
        WHERE is_active = TRUE
        ORDER BY name
        """
    )
    return [IndicatorResponse.model_validate(row) for row in rows]


async def get_indicator(indicator_id: str, database: Database) -> IndicatorResponse | None:
    row = await database.fetch_one(
        """
        SELECT id, name, category, unit, description, is_active
        FROM indicators
        WHERE id = %s AND is_active = TRUE
        """,
        (indicator_id,),
    )
    return IndicatorResponse.model_validate(row) if row is not None else None


async def list_sources(database: Database) -> list[SourceStatusResponse]:
    rows = await database.fetch_all(
        """
        SELECT
            source_metadata.source_key,
            source_metadata.name,
            source_metadata.source_url,
            source_metadata.refresh_interval_minutes,
            source_metadata.limitation,
            COALESCE(refresh_status.status, 'unavailable') AS status,
            refresh_status.last_attempt_at,
            refresh_status.last_success_at,
            refresh_status.stale_after_at
        FROM source_metadata
        LEFT JOIN refresh_status
            ON refresh_status.source_key = source_metadata.source_key
        ORDER BY source_metadata.name
        """
    )
    return [SourceStatusResponse.model_validate(row) for row in rows]


async def list_indicator_history(
    indicator_id: str, database: Database
) -> list[ObservationResponse]:
    rows = await database.fetch_all(
        """
        WITH latest_per_period AS (
            SELECT DISTINCT ON (period_label)
                indicator_id,
                source_key,
                period_label,
                observation_date,
                source_as_of_date,
                value,
                unit,
                comparison_value,
                comparison_period_label,
                collected_at
            FROM observations
            WHERE indicator_id = %s
                AND is_valid = TRUE
                AND (
                    source_key <> 'development_fixture'
                    OR NOT EXISTS (
                        SELECT 1
                        FROM observations AS live_observations
                        WHERE live_observations.indicator_id = observations.indicator_id
                            AND live_observations.is_valid = TRUE
                            AND live_observations.source_key <> 'development_fixture'
                    )
                )
            ORDER BY period_label, source_as_of_date DESC, collected_at DESC
        )
        SELECT *
        FROM latest_per_period
        ORDER BY observation_date ASC
        """,
        (indicator_id,),
    )
    return [ObservationResponse.model_validate(row) for row in rows]


async def build_dashboard(database: Database) -> DashboardResponse:
    rows = await database.fetch_all(
        """
        SELECT
            indicators.id,
            indicators.name,
            indicators.category,
            indicators.unit AS indicator_unit,
            indicators.description,
            indicators.is_active,
            COALESCE(observations.source_key, indicator_sources.source_key) AS source_key,
            observations.period_label,
            observations.observation_date,
            observations.source_as_of_date,
            observations.value,
            observations.unit AS observation_unit,
            observations.comparison_value,
            observations.comparison_period_label,
            source_metadata.name AS source_name,
            source_metadata.source_url,
            source_metadata.refresh_interval_minutes,
            source_metadata.limitation,
            COALESCE(refresh_status.status, 'unavailable') AS freshness_status,
            refresh_status.last_attempt_at,
            refresh_status.last_success_at,
            refresh_status.stale_after_at
        FROM indicators
        LEFT JOIN latest_valid_observations AS observations
            ON observations.indicator_id = indicators.id
        JOIN indicator_sources
            ON indicator_sources.indicator_id = indicators.id
        JOIN source_metadata
            ON source_metadata.source_key = COALESCE(observations.source_key, indicator_sources.source_key)
        LEFT JOIN refresh_status
            ON refresh_status.source_key = COALESCE(observations.source_key, indicator_sources.source_key)
        WHERE indicators.is_active = TRUE
        ORDER BY indicators.name
        """
    )

    ticker: list[MarketTickerItem] = []
    indicators: list[DashboardIndicatorResponse] = []

    for row in rows:
        source = SourceStatusResponse.model_validate(
            {
                "source_key": row["source_key"],
                "name": row["source_name"],
                "source_url": row["source_url"],
                "refresh_interval_minutes": row["refresh_interval_minutes"],
                "limitation": row["limitation"],
                "status": row["freshness_status"],
                "last_attempt_at": row["last_attempt_at"],
                "last_success_at": row["last_success_at"],
                "stale_after_at": row["stale_after_at"],
            }
        )

        if row["category"] == "market_ticker":
            ticker.append(
                MarketTickerItem(
                    symbol=str(row["name"]),
                    name=str(row["name"]),
                    last_price=float(row["value"]) if row["value"] is not None else None,
                    change=_calculate_change(row["value"], row["comparison_value"]),
                    change_percent=_calculate_change_percent(row["value"], row["comparison_value"]),
                    as_of=_as_utc_datetime(row["source_as_of_date"]),
                    freshness_status=row["freshness_status"],
                    source=source,
                )
            )
            continue

        indicator = IndicatorResponse(
            id=str(row["id"]),
            name=str(row["name"]),
            category=str(row["category"]),
            unit=str(row["indicator_unit"]),
            description=row["description"],
            is_active=bool(row["is_active"]),
        )
        history = await _history_points(str(row["id"]), database)
        status_message = _status_message(str(row["freshness_status"]), row["value"])
        indicators.append(
            DashboardIndicatorResponse(
                indicator=indicator,
                value=float(row["value"]) if row["value"] is not None else None,
                period_label=str(row["period_label"]) if row["period_label"] is not None else None,
                comparison_value=(
                    float(row["comparison_value"])
                    if row["comparison_value"] is not None
                    else None
                ),
                comparison_period_label=row["comparison_period_label"],
                change=_calculate_change(row["value"], row["comparison_value"]),
                change_percent=_calculate_change_percent(row["value"], row["comparison_value"]),
                as_of_date=row["source_as_of_date"],
                freshness_status=row["freshness_status"],
                source=source,
                history=history,
                message=status_message,
            )
        )

    return DashboardResponse(
        generated_at=datetime.now(timezone.utc),
        ticker=ticker,
        indicators=indicators,
    )


async def _history_points(indicator_id: str, database: Database) -> list[IndicatorHistoryPoint]:
    rows = await database.fetch_all(
        """
        WITH latest_per_period AS (
            SELECT DISTINCT ON (period_label)
                period_label,
                observation_date,
                value
            FROM observations
            WHERE indicator_id = %s
                AND is_valid = TRUE
                AND (
                    source_key <> 'development_fixture'
                    OR NOT EXISTS (
                        SELECT 1
                        FROM observations AS live_observations
                        WHERE live_observations.indicator_id = observations.indicator_id
                            AND live_observations.is_valid = TRUE
                            AND live_observations.source_key <> 'development_fixture'
                    )
                )
            ORDER BY period_label, source_as_of_date DESC, collected_at DESC
        )
        SELECT period_label, observation_date, value
        FROM latest_per_period
        ORDER BY observation_date ASC
        """,
        (indicator_id,),
    )
    return [IndicatorHistoryPoint.model_validate(row) for row in rows]


def _calculate_change(value: object, comparison_value: object) -> float | None:
    if value is None or comparison_value is None:
        return None
    return float(value) - float(comparison_value)


def _calculate_change_percent(value: object, comparison_value: object) -> float | None:
    if value is None or comparison_value in (None, 0):
        return None
    return ((float(value) - float(comparison_value)) / float(comparison_value)) * 100


def _as_utc_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)


def _status_message(freshness_status: str, value: object) -> str | None:
    if freshness_status == "stale":
        return "Showing the last valid observation because the most recent refresh failed."
    if freshness_status == "unavailable" or value is None:
        return "No validated observation is available from this source yet."
    return None
