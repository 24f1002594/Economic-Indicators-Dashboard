from __future__ import annotations

import argparse
import asyncio
from getpass import getpass

from app.auth import create_user
from app.db import database
from app.schemas import UserRole


async def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument("--role", choices=[role.value for role in UserRole], default=UserRole.VIEWER.value)
    arguments = parser.parse_args()

    password = getpass("Password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    await database.open()
    try:
        try:
            user = await create_user(
                email=arguments.email,
                password=password,
                role=UserRole(arguments.role),
                database=database,
            )
        except ValueError as error:
            raise SystemExit(str(error)) from error
    finally:
        await database.close()

    print(f"Created {user.role.value} account for {user.email}.")


if __name__ == "__main__":
    asyncio.run(run())
