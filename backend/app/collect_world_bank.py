from __future__ import annotations

import asyncio

from app.db import database
from app.services.collector_service import collect_world_bank_gdp


async def run() -> None:
    await database.open()
    try:
        result = await collect_world_bank_gdp(database)
    finally:
        await database.close()

    if not result.succeeded:
        raise SystemExit(f"World Bank GDP collection failed: {result.error}")
    print(
        f"World Bank GDP collection succeeded: {result.records_stored} of "
        f"{result.records_received} observations stored."
    )


if __name__ == "__main__":
    asyncio.run(run())
