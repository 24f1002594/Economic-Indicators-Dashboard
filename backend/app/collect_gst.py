from __future__ import annotations

import asyncio

from app.db import database
from app.services.collector_service import collect_gst_collection


async def run() -> None:
    await database.open()
    try:
        result = await collect_gst_collection(database)
    finally:
        await database.close()

    if not result.succeeded:
        raise SystemExit(f"GST collection failed: {result.error}")
    print(
        f"GST collection succeeded: {result.records_stored} of "
        f"{result.records_received} report rows stored."
    )


if __name__ == "__main__":
    asyncio.run(run())
