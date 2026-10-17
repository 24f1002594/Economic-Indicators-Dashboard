from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.db import Database, get_database
from app.schemas import UserResponse, UserRole


bearer_scheme = HTTPBearer(auto_error=False)
# Reads the authentication token from the request. auto_error=False allows your code to handle missing credentials itself.

def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if normalized.count("@") != 1 or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("Enter a valid email address.")
    return normalized

def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("Password must not exceed 72 bytes.")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        return False
    try:
        return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user: UserResponse) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_in = settings.access_token_expire_minutes * 60
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_in


def decode_access_token(token: str) -> dict[str, object]:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError as error:
        raise credentials_exception() from error


async def authenticate_user(email: str, password: str, database: Database) -> UserResponse | None:
    row = await database.fetch_one(
        """
        SELECT id, email, password_hash, role, is_active, created_at
        FROM users
        WHERE email = %s
        """,
        (normalize_email(email),),
    )
    if row is None or not verify_password(password, str(row["password_hash"])):
        return None
    if not bool(row["is_active"]):
        return None

    return UserResponse.model_validate(row)


async def create_user(
    email: str,
    password: str,
    role: UserRole,
    database: Database,
) -> UserResponse:
    normalized_email = normalize_email(email)
    existing_user = await database.fetch_one(
        "SELECT id FROM users WHERE email = %s",
        (normalized_email,),
    )
    if existing_user is not None:
        raise ValueError("A user with this email already exists.")

    row = await database.fetch_one(
        """
        INSERT INTO users (email, password_hash, role)
        VALUES (%s, %s, %s)
        RETURNING id, email, role, is_active, created_at
        """,
        (normalized_email, hash_password(password), role.value),
    )
    if row is None:
        raise RuntimeError("User creation did not return a user.")
    return UserResponse.model_validate(row)


def credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    database: Database = Depends(get_database),
) -> UserResponse:
    if credentials is None:
        raise credentials_exception()

    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdecimal():
        raise credentials_exception()

    row = await database.fetch_one(
        """
        SELECT id, email, role, is_active, created_at
        FROM users
        WHERE id = %s
        """,
        (int(subject),),
    )
    if row is None or not bool(row["is_active"]):
        raise credentials_exception()

    return UserResponse.model_validate(row)
