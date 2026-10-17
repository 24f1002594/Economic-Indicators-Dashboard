from __future__ import annotations

import asyncio

from app.db import database
from app.services.collector_service import collect_nse_ticker


async def run() -> None:
    await database.open()
    try:
        result = await collect_nse_ticker(database)
    finally:
        await database.close()

    if not result.succeeded:
        raise SystemExit(f"NSE collection failed: {result.error}")
    print(
        f"NSE collection succeeded: {result.records_stored} of "
        f"{result.records_received} observations stored."
    )


if __name__ == "__main__":
    asyncio.run(run())
