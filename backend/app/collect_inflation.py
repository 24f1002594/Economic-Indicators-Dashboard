from __future__ import annotations

import asyncio

from app.db import database
from app.services.collector_service import collect_inflation


async def run() -> None:
    await database.open()
    try:
        result = await collect_inflation(database)
    finally:
        await database.close()

    if not result.succeeded:
        raise SystemExit(f"Inflation collection failed: {result.error}")
    print(
        f"Inflation collection succeeded: {result.records_stored} of "
        f"{result.records_received} observations stored."
    )


if __name__ == "__main__":
    asyncio.run(run())
