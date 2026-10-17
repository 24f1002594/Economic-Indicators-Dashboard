from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta, timezone

from app.config import get_settings
from app.db import database


FIXTURE_SOURCE_KEY = "development_fixture"
FIXTURE_AS_OF_DATE = date(2026, 10, 1)

INDICATORS = [
    {
        "id": "gdp_growth_india",
        "name": "GDP Growth — India",
        "category": "gdp_growth",
        "unit": "%",
        "description": "Development fixture only. Replace with a validated public-source observation.",
    },
    {
        "id": "debt_to_gdp_india",
        "name": "Debt to GDP Ratio — India",
        "category": "debt_to_gdp",
        "unit": "%",
        "description": "Development fixture only. Replace with a validated public-source observation.",
    },
    {
        "id": "debt_to_gdp_us",
        "name": "Debt to GDP Ratio — US",
        "category": "debt_to_gdp",
        "unit": "%",
        "description": "Development fixture only. Replace with a validated public-source observation.",
    },
    {
        "id": "trade_balance_india",
        "name": "Imports, Exports and Trade Balance",
        "category": "trade",
        "unit": "USD billion",
        "description": "Development fixture only. The primary value represents trade balance.",
    },
    {
        "id": "gst_collection_india",
        "name": "GST Tax Collection",
        "category": "gst_collection",
        "unit": "₹ lakh crore",
        "description": "Development fixture only. Replace with a validated public-source observation.",
    },
    {
        "id": "inflation_india",
        "name": "Inflation — India",
        "category": "inflation",
        "unit": "%",
        "description": "Development fixture only. Replace with a validated public-source observation.",
    },
    {
        "id": "government_expenditure_india",
        "name": "Government Expenditure",
        "category": "government_expenditure",
        "unit": "₹ lakh crore",
        "description": "Development fixture only. The primary value represents total expenditure.",
    },
    {
        "id": "nifty_50",
        "name": "NIFTY 50",
        "category": "market_ticker",
        "unit": "points",
        "description": "Development fixture only. Replace with a validated NSE observation.",
    },
    {
        "id": "sensex",
        "name": "S&P BSE SENSEX",
        "category": "market_ticker",
        "unit": "points",
        "description": "Development fixture only. Replace with a validated NSE observation.",
    },
    {
        "id": "nifty_bank",
        "name": "NIFTY BANK",
        "category": "market_ticker",
        "unit": "points",
        "description": "Development fixture only. Replace with a validated NSE observation.",
    },
    {
        "id": "nifty_it",
        "name": "NIFTY IT",
        "category": "market_ticker",
        "unit": "points",
        "description": "Development fixture only. Replace with a validated NSE observation.",
    },
]

SERIES = {
    "gdp_growth_india": [("FY 2021-22", date(2022, 3, 31), 6.6), ("FY 2022-23", date(2023, 3, 31), 7.2), ("FY 2023-24", date(2024, 3, 31), 8.2), ("FY 2024-25", date(2025, 3, 31), 6.5), ("FY 2025-26", date(2026, 3, 31), 6.8)],
    "debt_to_gdp_india": [("FY 2021-22", date(2022, 3, 31), 87.0), ("FY 2022-23", date(2023, 3, 31), 84.0), ("FY 2023-24", date(2024, 3, 31), 82.5), ("FY 2024-25", date(2025, 3, 31), 81.3), ("FY 2025-26", date(2026, 3, 31), 80.9)],
    "debt_to_gdp_us": [("2021", date(2021, 12, 31), 122.6), ("2022", date(2022, 12, 31), 116.6), ("2023", date(2023, 12, 31), 114.7), ("2024", date(2024, 12, 31), 115.8)],
    "trade_balance_india": [("Jun 2025", date(2025, 6, 30), -21.7), ("Jul 2025", date(2025, 7, 31), -20.4), ("Aug 2025", date(2025, 8, 31), -24.0), ("Sep 2025", date(2025, 9, 30), -22.6), ("Oct 2025", date(2025, 10, 31), -23.1)],
    "gst_collection_india": [("Jun 2025", date(2025, 6, 30), 1.74), ("Jul 2025", date(2025, 7, 31), 1.82), ("Aug 2025", date(2025, 8, 31), 1.86), ("Sep 2025", date(2025, 9, 30), 1.89), ("Oct 2025", date(2025, 10, 31), 1.93)],
    "inflation_india": [("Jun 2025", date(2025, 6, 30), 4.1), ("Jul 2025", date(2025, 7, 31), 3.7), ("Aug 2025", date(2025, 8, 31), 3.4), ("Sep 2025", date(2025, 9, 30), 3.8), ("Oct 2025", date(2025, 10, 31), 4.2)],
    "government_expenditure_india": [("FY 2021-22", date(2022, 3, 31), 39.4), ("FY 2022-23", date(2023, 3, 31), 41.9), ("FY 2023-24", date(2024, 3, 31), 45.0), ("FY 2024-25", date(2025, 3, 31), 47.2), ("FY 2025-26", date(2026, 3, 31), 50.7)],
    "nifty_50": [("Fixture", FIXTURE_AS_OF_DATE, 23850.3)],
    "sensex": [("Fixture", FIXTURE_AS_OF_DATE, 78120.4)],
    "nifty_bank": [("Fixture", FIXTURE_AS_OF_DATE, 51240.8)],
    "nifty_it": [("Fixture", FIXTURE_AS_OF_DATE, 37842.15)],
}


async def seed_development_data() -> None:
    settings = get_settings()
    if settings.app_env != "development":
        raise SystemExit("Development fixtures can only run when APP_ENV=development.")

    fixture_metadata = json.dumps(
        {"fixture": True, "not_live": True, "seeded_at": datetime.now(timezone.utc).isoformat()}
    )

    await database.open()
    try:
        async with database.connection() as connection:
            await connection.execute(
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
                    FIXTURE_SOURCE_KEY,
                    "Development fixture data — not live",
                    "https://example.com/development-fixture",
                    60,
                    "Local development data only. It is not a public-source observation and must not be deployed.",
                ),
            )

            await connection.execute(
                """
                INSERT INTO refresh_status (
                    source_key, status, last_attempt_at, last_success_at, stale_after_at
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (source_key) DO UPDATE SET
                    status = EXCLUDED.status,
                    last_attempt_at = EXCLUDED.last_attempt_at,
                    last_success_at = EXCLUDED.last_success_at,
                    stale_after_at = EXCLUDED.stale_after_at,
                    last_error = NULL,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    FIXTURE_SOURCE_KEY,
                    "fresh",
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc) + timedelta(hours=1),
                ),
            )

            for indicator in INDICATORS:
                await connection.execute(
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
                        indicator["id"],
                        indicator["name"],
                        indicator["category"],
                        indicator["unit"],
                        indicator["description"],
                    ),
                )

                previous_value: float | None = None
                previous_label: str | None = None
                for period_label, observation_date, value in SERIES[indicator["id"]]:
                    await connection.execute(
                        """
                        INSERT INTO observations (
                            indicator_id,
                            source_key,
                            period_label,
                            observation_date,
                            source_as_of_date,
                            value,
                            unit,
                            comparison_value,
                            comparison_period_label,
                            raw_payload
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
                            indicator["id"],
                            FIXTURE_SOURCE_KEY,
                            period_label,
                            observation_date,
                            FIXTURE_AS_OF_DATE,
                            value,
                            indicator["unit"],
                            previous_value,
                            previous_label,
                            fixture_metadata,
                        ),
                    )
                    previous_value = value
                    previous_label = period_label
    finally:
        await database.close()

    print("Development fixture data is ready. Do not use it in production.")


if __name__ == "__main__":
    asyncio.run(seed_development_data())
