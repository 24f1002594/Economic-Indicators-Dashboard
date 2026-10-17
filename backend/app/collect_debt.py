from __future__ import annotations

import asyncio

from app.db import database
from app.services.collector_service import collect_debt_to_gdp


async def run() -> None:
    await database.open()
    try:
        result = await collect_debt_to_gdp(database)
    finally:
        await database.close()

    if not result.succeeded:
        raise SystemExit(f"Debt-to-GDP collection failed: {result.error}")
    print(
        f"Debt-to-GDP collection succeeded: {result.records_stored} of "
        f"{result.records_received} observations stored."
    )


if __name__ == "__main__":
    asyncio.run(run())
