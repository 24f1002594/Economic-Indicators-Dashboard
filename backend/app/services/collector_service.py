from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.db import Database
from app.services.validation_service import ObservationCandidate, validate_payload
from app.sources.nse import NSE_SOURCE_KEY, NseClient, NseSourceError, TRACKED_INDICES
from app.sources.gst import (
    GST_INDICATOR_ID,
    GST_NEWS_PATH,
    GST_SOURCE_KEY,
    GST_UNIT,
    GstClient,
    GstSourceError,
)
from app.sources.inflation import (
    INFLATION_INDICATOR_ID,
    INFLATION_UNIT,
    MOSPI_RELEASES_PATH,
    MOSPI_CPI_SOURCE_KEY,
    RBI_TARGET_BAND,
    RBI_TARGET_PERCENT,
    InflationClient,
    InflationSourceError,
)
from app.sources.expenditure import (
    BUDGET_AT_A_GLANCE_PATH,
    CAPITAL_EXPENDITURE_INDICATOR_ID,
    EXPENDITURE_SOURCE_KEY,
    EXPENDITURE_UNIT,
    TOTAL_EXPENDITURE_INDICATOR_ID,
    ExpenditureClient,
    ExpenditureSourceError,
)
from app.sources.debt import (
    DEBT_COUNTRY_TO_INDICATOR,
    DEBT_SOURCE_KEY,
    WORLD_BANK_DEBT_INDICATOR,
    DebtClient,
    DebtSourceError,
)
from app.sources.trade import (
    TRADE_INDICATORS,
    TRADE_REPORT_PATH,
    TRADE_SOURCE_KEY,
    TRADE_UNIT,
    TradeClient,
    TradeSourceError,
)
from app.sources.world_bank import (
    COUNTRY_TO_INDICATOR,
    WORLD_BANK_GDP_GROWTH_INDICATOR,
    WORLD_BANK_SOURCE_KEY,
    WorldBankClient,
    WorldBankSourceError,
)


_nse_collection_lock = asyncio.Lock()
_world_bank_collection_lock = asyncio.Lock()
_trade_collection_lock = asyncio.Lock()
_gst_collection_lock = asyncio.Lock()
_inflation_collection_lock = asyncio.Lock()
_expenditure_collection_lock = asyncio.Lock()
_debt_collection_lock = asyncio.Lock()


@dataclass(frozen=True)
class CollectionResult:
    source_key: str
    succeeded: bool
    records_received: int
    records_stored: int
    error: str | None = None


async def initialize_dashboard_metadata(database: Database) -> None:
    """Register every documented indicator and its primary public source.

    This runs independently of collection scheduling so a clean database can
    still describe all dashboard panels as unavailable rather than omitting
    them until its first successful upstream request.
    """

    await _ensure_nse_metadata(database)
    await _ensure_world_bank_gdp_metadata(database)
    await _ensure_debt_metadata(database)
    await _ensure_trade_metadata(database)
    await _ensure_gst_metadata(database)
    await _ensure_inflation_metadata(database)
    await _ensure_expenditure_metadata(database)


async def _bind_indicator_to_source(
    database: Database, indicator_id: str, source_key: str
) -> None:
    await database.execute(
        """
        INSERT INTO indicator_sources (indicator_id, source_key)
        VALUES (%s, %s)
        ON CONFLICT (indicator_id) DO UPDATE SET
            source_key = EXCLUDED.source_key,
            updated_at = CURRENT_TIMESTAMP
        """,
        (indicator_id, source_key),
    )


async def collect_nse_ticker(
    database: Database, client: NseClient | None = None
) -> CollectionResult:
    async with _nse_collection_lock:
        await _ensure_nse_metadata(database)
        run_id = await _start_collection_run(database, NSE_SOURCE_KEY)
        owned_client = client is None
        nse_client = client or NseClient()

        try:
            quotes = await nse_client.fetch_quotes()
            validated_observations = _validated_nse_observations(quotes)
            await _store_observations(database, validated_observations)
            await _mark_collection_succeeded(
                database,
                NSE_SOURCE_KEY,
                run_id,
                len(quotes),
                len(validated_observations),
                get_settings().collector_interval_minutes,
            )
            return CollectionResult(
                source_key=NSE_SOURCE_KEY,
                succeeded=True,
                records_received=len(quotes),
                records_stored=len(validated_observations),
            )
        except (NseSourceError, RuntimeError, ValueError) as error:
            message = str(error)[:1_000]
            await _mark_collection_failed(database, NSE_SOURCE_KEY, run_id, message)
            return CollectionResult(
                source_key=NSE_SOURCE_KEY,
                succeeded=False,
                records_received=0,
                records_stored=0,
                error=message,
            )
        finally:
            if owned_client:
                await nse_client.close()


async def _ensure_nse_metadata(database: Database) -> None:
    await database.execute(
        """
        INSERT INTO source_metadata (
            source_key, name, source_url, refresh_interval_minutes, limitation
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (source_key) DO UPDATE SET
            name = EXCLUDED.name,
            source_url = EXCLUDED.source_url,
            refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
            limitation = EXCLUDED.limitation,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            NSE_SOURCE_KEY,
            "NSE all-indices endpoint",
            f"{get_settings().nse_base_url.rstrip('/')}/api/allIndices",
            get_settings().collector_interval_minutes,
            "Public endpoint response shape and availability may change. Refreshes are rate-limited by the server-side collector.",
        ),
    )

    for _, (indicator_id, name) in TRACKED_INDICES.items():
        await database.execute(
            """
            INSERT INTO indicators (id, name, category, unit, description)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                category = EXCLUDED.category,
                unit = EXCLUDED.unit,
                description = EXCLUDED.description,
                is_active = TRUE,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                indicator_id,
                name,
                "market_ticker",
                "points",
                "Live value collected server-side from NSE.",
            ),
        )
        await _bind_indicator_to_source(database, indicator_id, NSE_SOURCE_KEY)


async def collect_world_bank_gdp(
    database: Database, client: WorldBankClient | None = None
) -> CollectionResult:
    async with _world_bank_collection_lock:
        await _ensure_world_bank_gdp_metadata(database)
        run_id = await _start_collection_run(database, WORLD_BANK_SOURCE_KEY)
        owned_client = client is None
        world_bank_client = client or WorldBankClient()

        try:
            points = await world_bank_client.fetch_gdp_growth()
            validated_observations = _validated_world_bank_observations(points)
            await _store_observations(database, validated_observations)
            await _mark_collection_succeeded(
                database,
                WORLD_BANK_SOURCE_KEY,
                run_id,
                len(points),
                len(validated_observations),
                1_440,
            )
            return CollectionResult(
                source_key=WORLD_BANK_SOURCE_KEY,
                succeeded=True,
                records_received=len(points),
                records_stored=len(validated_observations),
            )
        except (WorldBankSourceError, RuntimeError, ValueError) as error:
            message = str(error)[:1_000]
            await _mark_collection_failed(database, WORLD_BANK_SOURCE_KEY, run_id, message)
            return CollectionResult(
                source_key=WORLD_BANK_SOURCE_KEY,
                succeeded=False,
                records_received=0,
                records_stored=0,
                error=message,
            )
        finally:
            if owned_client:
                await world_bank_client.close()


async def collect_debt_to_gdp(
    database: Database, client: DebtClient | None = None
) -> CollectionResult:
    async with _debt_collection_lock:
        await _ensure_debt_metadata(database)
        run_id = await _start_collection_run(database, DEBT_SOURCE_KEY)
        owned_client = client is None
        debt_client = client or DebtClient()

        try:
            points = await debt_client.fetch_debt_to_gdp()
            validated_observations = _validated_debt_observations(points)
            await _store_observations(database, validated_observations)
            await _mark_collection_succeeded(
                database,
                DEBT_SOURCE_KEY,
                run_id,
                len(points),
                len(validated_observations),
                1_440,
            )
            return CollectionResult(
                source_key=DEBT_SOURCE_KEY,
                succeeded=True,
                records_received=len(points),
                records_stored=len(validated_observations),
            )
        except (DebtSourceError, RuntimeError, ValueError) as error:
            message = str(error)[:1_000]
            await _mark_collection_failed(database, DEBT_SOURCE_KEY, run_id, message)
            return CollectionResult(
                source_key=DEBT_SOURCE_KEY,
                succeeded=False,
                records_received=0,
                records_stored=0,
                error=message,
            )
        finally:
            if owned_client:
                await debt_client.close()


async def collect_monthly_trade(
    database: Database, client: TradeClient | None = None
) -> CollectionResult:
    async with _trade_collection_lock:
        await _ensure_trade_metadata(database)
        run_id = await _start_collection_run(database, TRADE_SOURCE_KEY)
        owned_client = client is None
        trade_client = client or TradeClient()

        try:
            points = await trade_client.fetch_recent_monthly_trade()
            validated_observations = [
                observation
                for point in points
                for observation in _validated_trade_observations(point)
            ]
            await _store_observations(database, validated_observations)
            await _mark_collection_succeeded(
                database,
                TRADE_SOURCE_KEY,
                run_id,
                len(points),
                len(validated_observations),
                get_settings().trade_refresh_hours * 60,
            )
            return CollectionResult(
                source_key=TRADE_SOURCE_KEY,
                succeeded=True,
                records_received=len(points),
                records_stored=len(validated_observations),
            )
        except (TradeSourceError, RuntimeError, ValueError) as error:
            message = str(error)[:1_000]
            await _mark_collection_failed(database, TRADE_SOURCE_KEY, run_id, message)
            return CollectionResult(
                source_key=TRADE_SOURCE_KEY,
                succeeded=False,
                records_received=0,
                records_stored=0,
                error=message,
            )
        finally:
            if owned_client:
                await trade_client.close()


async def collect_gst_collection(
    database: Database, client: GstClient | None = None
) -> CollectionResult:
    async with _gst_collection_lock:
        await _ensure_gst_metadata(database)
        run_id = await _start_collection_run(database, GST_SOURCE_KEY)
        owned_client = client is None
        gst_client = client or GstClient()

        try:
            points = await gst_client.fetch_recent_collections()
            validated_observations = [_validated_gst_observation(point) for point in points]
            await _store_observations(database, validated_observations)
            await _mark_collection_succeeded(
                database,
                GST_SOURCE_KEY,
                run_id,
                len(points),
                len(validated_observations),
                get_settings().gst_refresh_hours * 60,
            )
            return CollectionResult(
                source_key=GST_SOURCE_KEY,
                succeeded=True,
                records_received=len(points),
                records_stored=len(validated_observations),
            )
        except (GstSourceError, RuntimeError, ValueError) as error:
            message = str(error)[:1_000]
            await _mark_collection_failed(database, GST_SOURCE_KEY, run_id, message)
            return CollectionResult(
                source_key=GST_SOURCE_KEY,
                succeeded=False,
                records_received=0,
                records_stored=0,
                error=message,
            )
        finally:
            if owned_client:
                await gst_client.close()


async def collect_inflation(
    database: Database, client: InflationClient | None = None
) -> CollectionResult:
    async with _inflation_collection_lock:
        await _ensure_inflation_metadata(database)
        run_id = await _start_collection_run(database, MOSPI_CPI_SOURCE_KEY)
        owned_client = client is None
        inflation_client = client or InflationClient()

        try:
            points = await inflation_client.fetch_combined_cpi_inflation()
            validated_observations = _validated_inflation_observations(points)
            await _store_observations(database, validated_observations)
            await _mark_collection_succeeded(
                database,
                MOSPI_CPI_SOURCE_KEY,
                run_id,
                len(points),
                len(validated_observations),
                get_settings().inflation_refresh_hours * 60,
            )
            return CollectionResult(
                source_key=MOSPI_CPI_SOURCE_KEY,
                succeeded=True,
                records_received=len(points),
                records_stored=len(validated_observations),
            )
        except (InflationSourceError, RuntimeError, ValueError) as error:
            message = str(error)[:1_000]
            await _mark_collection_failed(database, MOSPI_CPI_SOURCE_KEY, run_id, message)
            return CollectionResult(
                source_key=MOSPI_CPI_SOURCE_KEY,
                succeeded=False,
                records_received=0,
                records_stored=0,
                error=message,
            )
        finally:
            if owned_client:
                await inflation_client.close()


async def collect_government_expenditure(
    database: Database, client: ExpenditureClient | None = None
) -> CollectionResult:
    async with _expenditure_collection_lock:
        await _ensure_expenditure_metadata(database)
        run_id = await _start_collection_run(database, EXPENDITURE_SOURCE_KEY)
        owned_client = client is None
        expenditure_client = client or ExpenditureClient()

        try:
            points = await expenditure_client.fetch_latest_expenditure()
            validated_observations = _validated_expenditure_observations(points)
            await _store_observations(database, validated_observations)
            await _mark_collection_succeeded(
                database,
                EXPENDITURE_SOURCE_KEY,
                run_id,
                len(points),
                len(validated_observations),
                get_settings().expenditure_refresh_hours * 60,
            )
            return CollectionResult(
                source_key=EXPENDITURE_SOURCE_KEY,
                succeeded=True,
                records_received=len(points),
                records_stored=len(validated_observations),
            )
        except (ExpenditureSourceError, RuntimeError, ValueError) as error:
            message = str(error)[:1_000]
            await _mark_collection_failed(database, EXPENDITURE_SOURCE_KEY, run_id, message)
            return CollectionResult(
                source_key=EXPENDITURE_SOURCE_KEY,
                succeeded=False,
                records_received=0,
                records_stored=0,
                error=message,
            )
        finally:
            if owned_client:
                await expenditure_client.close()


async def _start_collection_run(database: Database, source_key: str) -> int:
    row = await database.fetch_one(
        """
        INSERT INTO collection_runs (source_key, status)
        VALUES (%s, 'running')
        RETURNING id
        """,
        (source_key,),
    )
    if row is None:
        raise RuntimeError("Could not create an NSE collection run.")
    return int(row["id"])


def _validated_nse_observations(quotes: list[object]) -> list[ObservationCandidate]:
    validated: list[ObservationCandidate] = []
    for quote in quotes:
        comparison_value = None
        comparison_period_label = None
        change = getattr(quote, "change")
        if change is not None:
            comparison_value = getattr(quote, "last_price") - change
            comparison_period_label = "Previous close"

        payload = {
            "indicator_id": getattr(quote, "indicator_id"),
            "source_key": NSE_SOURCE_KEY,
            "period_label": getattr(quote, "as_of_date").isoformat(),
            "observation_date": getattr(quote, "as_of_date"),
            "source_as_of_date": getattr(quote, "as_of_date"),
            "value": getattr(quote, "last_price"),
            "unit": "points",
            "comparison_value": comparison_value,
            "comparison_period_label": comparison_period_label,
            "raw_payload": getattr(quote, "raw_payload"),
        }
        result = validate_payload(payload)
        if not result.is_valid or result.observation is None:
            raise NseSourceError("NSE observation validation failed: " + "; ".join(result.errors))
        validated.append(result.observation)
    return validated


def _validated_world_bank_observations(points: list[object]) -> list[ObservationCandidate]:
    previous_by_indicator: dict[str, tuple[float, str]] = {}
    validated: list[ObservationCandidate] = []
    for point in sorted(points, key=lambda point: (getattr(point, "indicator_id"), getattr(point, "year"))):
        indicator_id = getattr(point, "indicator_id")
        previous = previous_by_indicator.get(indicator_id)
        payload = {
            "indicator_id": indicator_id,
            "source_key": WORLD_BANK_SOURCE_KEY,
            "period_label": str(getattr(point, "year")),
            "observation_date": datetime(getattr(point, "year"), 12, 31).date(),
            "source_as_of_date": getattr(point, "source_as_of_date"),
            "value": getattr(point, "value"),
            "unit": "%",
            "comparison_value": previous[0] if previous else None,
            "comparison_period_label": previous[1] if previous else None,
            "raw_payload": getattr(point, "raw_payload"),
        }
        result = validate_payload(payload)
        if not result.is_valid or result.observation is None:
            raise WorldBankSourceError(
                "World Bank GDP observation validation failed: " + "; ".join(result.errors)
            )
        validated.append(result.observation)
        previous_by_indicator[indicator_id] = (float(getattr(point, "value")), str(getattr(point, "year")))
    return validated


def _validated_debt_observations(points: list[object]) -> list[ObservationCandidate]:
    previous_by_indicator: dict[str, tuple[float, str]] = {}
    observations: list[ObservationCandidate] = []
    for point in sorted(points, key=lambda point: (getattr(point, "indicator_id"), getattr(point, "year"))):
        indicator_id = getattr(point, "indicator_id")
        previous = previous_by_indicator.get(indicator_id)
        payload = {
            "indicator_id": indicator_id,
            "source_key": DEBT_SOURCE_KEY,
            "period_label": str(getattr(point, "year")),
            "observation_date": datetime(getattr(point, "year"), 12, 31).date(),
            "source_as_of_date": getattr(point, "source_as_of_date"),
            "value": getattr(point, "value"),
            "unit": "%",
            "comparison_value": previous[0] if previous else None,
            "comparison_period_label": previous[1] if previous else None,
            "raw_payload": getattr(point, "raw_payload"),
        }
        result = validate_payload(payload)
        if not result.is_valid or result.observation is None:
            raise DebtSourceError(
                "World Bank debt-to-GDP observation validation failed: "
                + "; ".join(result.errors)
            )
        observations.append(result.observation)
        previous_by_indicator[indicator_id] = (float(getattr(point, "value")), str(getattr(point, "year")))
    return observations


def _validated_trade_observations(point: object) -> list[ObservationCandidate]:
    values = {
        "exports_india": float(getattr(point, "exports_usd_millions")) / 1_000,
        "imports_india": float(getattr(point, "imports_usd_millions")) / 1_000,
    }
    values["trade_balance_india"] = values["exports_india"] - values["imports_india"]
    observations: list[ObservationCandidate] = []
    for indicator_id, value in values.items():
        payload = {
            "indicator_id": indicator_id,
            "source_key": TRADE_SOURCE_KEY,
            "period_label": getattr(point, "period_label"),
            "observation_date": getattr(point, "observation_date"),
            "source_as_of_date": getattr(point, "source_as_of_date"),
            "value": value,
            "unit": TRADE_UNIT,
            "comparison_value": None,
            "comparison_period_label": None,
            "raw_payload": getattr(point, "raw_payload"),
        }
        result = validate_payload(payload)
        if not result.is_valid or result.observation is None:
            raise TradeSourceError(
                "Department of Commerce trade observation validation failed: "
                + "; ".join(result.errors)
            )
        observations.append(result.observation)
    return observations


def _validated_gst_observation(point: object) -> ObservationCandidate:
    payload = {
        "indicator_id": GST_INDICATOR_ID,
        "source_key": GST_SOURCE_KEY,
        "period_label": getattr(point, "period_label"),
        "observation_date": getattr(point, "observation_date"),
        "source_as_of_date": getattr(point, "source_as_of_date"),
        "value": getattr(point, "gross_collection_lakh_crore"),
        "unit": GST_UNIT,
        "comparison_value": getattr(point, "previous_year_collection_lakh_crore"),
        "comparison_period_label": getattr(point, "comparison_period_label"),
        "raw_payload": getattr(point, "raw_payload"),
    }
    result = validate_payload(payload)
    if not result.is_valid or result.observation is None:
        raise GstSourceError(
            "GST collection observation validation failed: " + "; ".join(result.errors)
        )
    return result.observation


def _validated_inflation_observations(points: list[object]) -> list[ObservationCandidate]:
    observations: list[ObservationCandidate] = []
    for point in points:
        payload = {
            "indicator_id": INFLATION_INDICATOR_ID,
            "source_key": MOSPI_CPI_SOURCE_KEY,
            "period_label": getattr(point, "period_label"),
            "observation_date": getattr(point, "observation_date"),
            "source_as_of_date": getattr(point, "source_as_of_date"),
            "value": getattr(point, "inflation_percent"),
            "unit": INFLATION_UNIT,
            "comparison_value": RBI_TARGET_PERCENT,
            "comparison_period_label": f"RBI target ({RBI_TARGET_BAND} tolerance band)",
            "raw_payload": getattr(point, "raw_payload"),
        }
        result = validate_payload(payload)
        if not result.is_valid or result.observation is None:
            raise InflationSourceError(
                "MoSPI CPI observation validation failed: " + "; ".join(result.errors)
            )
        observations.append(result.observation)
    return observations


def _validated_expenditure_observations(points: list[object]) -> list[ObservationCandidate]:
    observations: list[ObservationCandidate] = []
    for point in points:
        payload = {
            "indicator_id": getattr(point, "indicator_id"),
            "source_key": EXPENDITURE_SOURCE_KEY,
            "period_label": getattr(point, "period_label"),
            "observation_date": getattr(point, "observation_date"),
            "source_as_of_date": getattr(point, "source_as_of_date"),
            "value": getattr(point, "value_lakh_crore"),
            "unit": EXPENDITURE_UNIT,
            "comparison_value": getattr(point, "comparison_value_lakh_crore"),
            "comparison_period_label": getattr(point, "comparison_period_label"),
            "raw_payload": getattr(point, "raw_payload"),
        }
        result = validate_payload(payload)
        if not result.is_valid or result.observation is None:
            raise ExpenditureSourceError(
                "Union Budget expenditure observation validation failed: "
                + "; ".join(result.errors)
            )
        observations.append(result.observation)
    return observations


async def _store_observations(
    database: Database, observations: list[ObservationCandidate]
) -> None:
    async with database.connection() as connection:
        for observation in observations:
            await connection.execute(
                """
                INSERT INTO observations (
                    indicator_id, source_key, period_label, observation_date,
                    source_as_of_date, value, unit, comparison_value,
                    comparison_period_label, raw_payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (indicator_id, source_key, period_label, source_as_of_date)
                DO UPDATE SET
                    observation_date = EXCLUDED.observation_date,
                    value = EXCLUDED.value,
                    unit = EXCLUDED.unit,
                    comparison_value = EXCLUDED.comparison_value,
                    comparison_period_label = EXCLUDED.comparison_period_label,
                    collected_at = CURRENT_TIMESTAMP,
                    is_valid = TRUE,
                    validation_notes = NULL,
                    raw_payload = EXCLUDED.raw_payload
                """,
                (
                    observation.indicator_id,
                    observation.source_key,
                    observation.period_label,
                    observation.observation_date,
                    observation.source_as_of_date,
                    observation.value,
                    observation.unit,
                    observation.comparison_value,
                    observation.comparison_period_label,
                    json.dumps(observation.raw_payload),
                ),
            )


async def _mark_collection_succeeded(
    database: Database,
    source_key: str,
    run_id: int,
    records_received: int,
    records_stored: int,
    refresh_interval_minutes: int,
) -> None:
    now = datetime.now(timezone.utc)
    stale_after = now + timedelta(minutes=refresh_interval_minutes * 2)
    await database.execute(
        """
        UPDATE collection_runs
        SET status = 'succeeded', completed_at = %s, records_received = %s, records_stored = %s
        WHERE id = %s
        """,
        (now, records_received, records_stored, run_id),
    )
    await database.execute(
        """
        INSERT INTO refresh_status (
            source_key, status, last_attempt_at, last_success_at, stale_after_at, last_error
        )
        VALUES (%s, 'fresh', %s, %s, %s, NULL)
        ON CONFLICT (source_key) DO UPDATE SET
            status = EXCLUDED.status,
            last_attempt_at = EXCLUDED.last_attempt_at,
            last_success_at = EXCLUDED.last_success_at,
            stale_after_at = EXCLUDED.stale_after_at,
            last_error = NULL,
            updated_at = CURRENT_TIMESTAMP
        """,
        (source_key, now, now, stale_after),
    )


async def _mark_collection_failed(
    database: Database, source_key: str, run_id: int, error_message: str
) -> None:
    now = datetime.now(timezone.utc)
    existing = await database.fetch_one(
        """
        SELECT EXISTS (
            SELECT 1 FROM observations WHERE source_key = %s AND is_valid = TRUE
        ) AS has_valid_observation
        """,
        (source_key,),
    )
    status_value = "stale" if existing and existing["has_valid_observation"] else "unavailable"
    await database.execute(
        """
        UPDATE collection_runs
        SET status = 'failed', completed_at = %s, error_message = %s
        WHERE id = %s
        """,
        (now, error_message, run_id),
    )
    await database.execute(
        """
        INSERT INTO refresh_status (source_key, status, last_attempt_at, last_error)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (source_key) DO UPDATE SET
            status = EXCLUDED.status,
            last_attempt_at = EXCLUDED.last_attempt_at,
            last_error = EXCLUDED.last_error,
            updated_at = CURRENT_TIMESTAMP
        """,
        (source_key, status_value, now, error_message),
    )


async def _ensure_world_bank_gdp_metadata(database: Database) -> None:
    await database.execute(
        """
        INSERT INTO source_metadata (
            source_key, name, source_url, refresh_interval_minutes, limitation
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (source_key) DO UPDATE SET
            name = EXCLUDED.name,
            source_url = EXCLUDED.source_url,
            refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
            limitation = EXCLUDED.limitation,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            WORLD_BANK_SOURCE_KEY,
            "World Bank GDP growth API",
            f"{get_settings().world_bank_base_url.rstrip('/')}/v2/country/IND;WLD/indicator/{WORLD_BANK_GDP_GROWTH_INDICATOR}?format=json",
            1_440,
            "Annual GDP growth data can be revised and may have a publication lag.",
        ),
    )
    for _, (indicator_id, name) in COUNTRY_TO_INDICATOR.items():
        await database.execute(
            """
            INSERT INTO indicators (id, name, category, unit, description)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                category = EXCLUDED.category,
                unit = EXCLUDED.unit,
                description = EXCLUDED.description,
                is_active = TRUE,
                updated_at = CURRENT_TIMESTAMP
            """,
            (indicator_id, name, "gdp_growth", "%", "Annual GDP growth from the World Bank."),
        )
        await _bind_indicator_to_source(database, indicator_id, WORLD_BANK_SOURCE_KEY)


async def _ensure_debt_metadata(database: Database) -> None:
    await database.execute(
        """
        INSERT INTO source_metadata (
            source_key, name, source_url, refresh_interval_minutes, limitation
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (source_key) DO UPDATE SET
            name = EXCLUDED.name,
            source_url = EXCLUDED.source_url,
            refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
            limitation = EXCLUDED.limitation,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            DEBT_SOURCE_KEY,
            "World Bank central government debt API",
            f"{get_settings().world_bank_base_url.rstrip('/')}/v2/country/IND;USA/indicator/{WORLD_BANK_DEBT_INDICATOR}?format=json",
            1_440,
            "The World Bank series is central government debt as a share of GDP. It currently has a substantial publication lag for India, and India/US observations can be published for different years; the dashboard shows each country's latest published observation and its year.",
        ),
    )
    for indicator_id, name in DEBT_COUNTRY_TO_INDICATOR.values():
        await database.execute(
            """
            INSERT INTO indicators (id, name, category, unit, description)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                category = EXCLUDED.category,
                unit = EXCLUDED.unit,
                description = EXCLUDED.description,
                is_active = TRUE,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                indicator_id,
                name,
                "debt_to_gdp",
                "%",
                "Central government debt as a share of GDP from the World Bank's latest published observation.",
            ),
        )
        await _bind_indicator_to_source(database, indicator_id, DEBT_SOURCE_KEY)


async def _ensure_trade_metadata(database: Database) -> None:
    settings = get_settings()
    await database.execute(
        """
        INSERT INTO source_metadata (
            source_key, name, source_url, refresh_interval_minutes, limitation
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (source_key) DO UPDATE SET
            name = EXCLUDED.name,
            source_url = EXCLUDED.source_url,
            refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
            limitation = EXCLUDED.limitation,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            TRADE_SOURCE_KEY,
            "Department of Commerce monthly trade report",
            f"{settings.trade_base_url.rstrip('/')}{TRADE_REPORT_PATH}",
            settings.trade_refresh_hours * 60,
            "Monthly USD values are converted to USD billion. The public report can be revised, delayed, or temporarily return no data.",
        ),
    )
    for indicator_id, name in TRADE_INDICATORS.items():
        await database.execute(
            """
            INSERT INTO indicators (id, name, category, unit, description)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                category = EXCLUDED.category,
                unit = EXCLUDED.unit,
                description = EXCLUDED.description,
                is_active = TRUE,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                indicator_id,
                name,
                "trade",
                TRADE_UNIT,
                "Monthly merchandise trade from the Department of Commerce, shown in USD billion.",
            ),
        )
        await _bind_indicator_to_source(database, indicator_id, TRADE_SOURCE_KEY)


async def _ensure_gst_metadata(database: Database) -> None:
    settings = get_settings()
    await database.execute(
        """
        INSERT INTO source_metadata (
            source_key, name, source_url, refresh_interval_minutes, limitation
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (source_key) DO UPDATE SET
            name = EXCLUDED.name,
            source_url = EXCLUDED.source_url,
            refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
            limitation = EXCLUDED.limitation,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            GST_SOURCE_KEY,
            "GST Portal monthly collection releases",
            f"{settings.gst_base_url.rstrip('/')}{GST_NEWS_PATH}",
            settings.gst_refresh_hours * 60,
            "Gross GST revenue is converted from the official report's ₹ crore unit to ₹ lakh crore. Releases are provisional and may be revised.",
        ),
    )
    await database.execute(
        """
        INSERT INTO indicators (id, name, category, unit, description)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            category = EXCLUDED.category,
            unit = EXCLUDED.unit,
            description = EXCLUDED.description,
            is_active = TRUE,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            GST_INDICATOR_ID,
            "GST Tax Collection",
            "gst_collection",
            GST_UNIT,
            "Monthly total gross GST revenue from GSTN, shown in ₹ lakh crore.",
        ),
    )
    await _bind_indicator_to_source(database, GST_INDICATOR_ID, GST_SOURCE_KEY)


async def _ensure_inflation_metadata(database: Database) -> None:
    settings = get_settings()
    await database.execute(
        """
        INSERT INTO source_metadata (
            source_key, name, source_url, refresh_interval_minutes, limitation
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (source_key) DO UPDATE SET
            name = EXCLUDED.name,
            source_url = EXCLUDED.source_url,
            refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
            limitation = EXCLUDED.limitation,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            MOSPI_CPI_SOURCE_KEY,
            "MoSPI all-India combined CPI inflation catalogue",
            f"{settings.mospi_base_url.rstrip('/')}{MOSPI_RELEASES_PATH}",
            settings.inflation_refresh_hours * 60,
            "CPI readings can be provisional and may be revised in later MoSPI releases.",
        ),
    )
    await database.execute(
        """
        INSERT INTO indicators (id, name, category, unit, description)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            category = EXCLUDED.category,
            unit = EXCLUDED.unit,
            description = EXCLUDED.description,
            is_active = TRUE,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            INFLATION_INDICATOR_ID,
            "Inflation — India",
            "inflation",
            INFLATION_UNIT,
            "All-India combined CPI inflation from MoSPI. The comparison field is the RBI's 4% target with a 2%–6% tolerance band.",
        ),
    )
    await _bind_indicator_to_source(database, INFLATION_INDICATOR_ID, MOSPI_CPI_SOURCE_KEY)


async def _ensure_expenditure_metadata(database: Database) -> None:
    settings = get_settings()
    await database.execute(
        """
        INSERT INTO source_metadata (
            source_key, name, source_url, refresh_interval_minutes, limitation
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (source_key) DO UPDATE SET
            name = EXCLUDED.name,
            source_url = EXCLUDED.source_url,
            refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
            limitation = EXCLUDED.limitation,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            EXPENDITURE_SOURCE_KEY,
            "Union Budget at a Glance",
            f"{settings.expenditure_base_url.rstrip('/')}{BUDGET_AT_A_GLANCE_PATH}",
            settings.expenditure_refresh_hours * 60,
            "Budget Estimates are planned annual spending, not final actual expenditure. The document is replaced when a new Union Budget is published.",
        ),
    )
    indicators = [
        (
            TOTAL_EXPENDITURE_INDICATOR_ID,
            "Government Expenditure",
            "Total Union Government expenditure in the annual Budget Estimate, shown in ₹ lakh crore.",
        ),
        (
            CAPITAL_EXPENDITURE_INDICATOR_ID,
            "Government Capital Expenditure",
            "Union Government capital expenditure in the annual Budget Estimate, shown in ₹ lakh crore.",
        ),
    ]
    for indicator_id, name, description in indicators:
        await database.execute(
            """
            INSERT INTO indicators (id, name, category, unit, description)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                category = EXCLUDED.category,
                unit = EXCLUDED.unit,
                description = EXCLUDED.description,
                is_active = TRUE,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                indicator_id,
                name,
                "government_expenditure",
                EXPENDITURE_UNIT,
                description,
            ),
        )
        await _bind_indicator_to_source(database, indicator_id, EXPENDITURE_SOURCE_KEY)
