from __future__ import annotations

import asyncio
from pathlib import Path

from psycopg import AsyncConnection

from app.config import get_settings


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


async def run_migrations() -> None:
    settings = get_settings()
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    async with await AsyncConnection.connect(str(settings.database_url)) as connection:
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        for migration_file in migration_files:
            existing = await connection.execute(
                "SELECT filename FROM schema_migrations WHERE filename = %s",
                (migration_file.name,),
            )
            if await existing.fetchone():
                continue

            await connection.execute(migration_file.read_text(encoding="utf-8"))
            await connection.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)",
                (migration_file.name,),
            )
            await connection.commit()
            print(f"Applied {migration_file.name}")


if __name__ == "__main__":
    asyncio.run(run_migrations())
