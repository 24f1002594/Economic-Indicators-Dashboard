from __future__ import annotations

import asyncio

from app.db import database
from app.services.collector_service import collect_monthly_trade


async def run() -> None:
    await database.open()
    try:
        result = await collect_monthly_trade(database)
    finally:
        await database.close()

    if not result.succeeded:
        raise SystemExit(f"Monthly trade collection failed: {result.error}")
    print(
        f"Monthly trade collection succeeded: {result.records_stored} of "
        f"{result.records_received} report rows stored."
    )


if __name__ == "__main__":
    asyncio.run(run())
