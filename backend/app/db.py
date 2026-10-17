from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager

from psycopg import AsyncConnection   
# Allows your backend to communicate with PostgreSQL asynchronously
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool 
# Reuses database connections instead of creating a new one for every request. It allows between 1 and 10 connections.

from app.config import get_settings


QueryParameters = Mapping[str, object] | Sequence[object] | None


class Database:
    def __init__(self) -> None:
        self._pool: AsyncConnectionPool | None = None

    # Opens the database connection pool when the application starts.
    async def open(self) -> None:
        if self._pool is not None:
            return

        settings = get_settings()
        self._pool = AsyncConnectionPool(
            conninfo=str(settings.database_url),
            min_size=1,
            max_size=10,
            open=False,
            kwargs={"row_factory": dict_row},
        )
        await self._pool.open()
        await self._pool.wait()

    # Closes the pool when the application shuts down.
    async def close(self) -> None:  
        if self._pool is None:
            return

        await self._pool.close()
        self._pool = None

    # Provides a database connection when needed.
    @asynccontextmanager
    async def connection(self) -> AsyncIterator[AsyncConnection]: 
        if self._pool is None:
            raise RuntimeError("Database pool is not open.")

        async with self._pool.connection() as connection:
            yield connection

    # Retrieves one row from the database.
    async def fetch_one( 
        self, query: str, parameters: QueryParameters = None
    ) -> dict[str, object] | None:
        async with self.connection() as connection:
            cursor = await connection.execute(query, parameters)
            return await cursor.fetchone()

    # Retrieves all rows from the database.
    async def fetch_all( 
        self, query: str, parameters: QueryParameters = None
    ) -> list[dict[str, object]]:
        async with self.connection() as connection:
            cursor = await connection.execute(query, parameters)
            return await cursor.fetchall()

    # Executes a query that modifies the database (like INSERT, UPDATE, DELETE) and returns the number of affected rows.
    async def execute(self, query: str, parameters: QueryParameters = None) -> int:
        async with self.connection() as connection:
            cursor = await connection.execute(query, parameters)
            return cursor.rowcount

    # Checks if the database connection is alive by executing a simple query.
    async def ping(self) -> bool:
        row = await self.fetch_one("SELECT 1 AS database_ok")
        return row == {"database_ok": 1}


database = Database() # Create an instance of the Database class


def get_database() -> Database: # Return the database instance for use in other parts of the application.
    return database
