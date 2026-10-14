from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.deps import get_db

bearer_scheme = HTTPBearer()

# Fails fast at import time if FERNET_KEY is missing/invalid, instead of
# silently minting a new key every restart (which would make previously
# encrypted data permanently undecryptable).
fernet = Fernet(settings.fernet_key.encode())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed_password.encode())
    except ValueError:
        # Malformed hash in the DB shouldn't crash the request.
        return False


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def _resolve_user_from_credentials(
    credentials: HTTPAuthorizationCredentials, db: AsyncSession
):
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    from app.models.user import User  # local import to avoid a circular import at module load

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    return await _resolve_user_from_credentials(credentials, db)


async def get_current_user_with_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Like get_current_user, but also returns the raw bearer token so callers
    (e.g. logout) can act on the specific session instead of every session
    belonging to the user."""
    user = await _resolve_user_from_credentials(credentials, db)
    return user, credentials.credentials


def encrypt_data(data: str | None) -> str | None:
    if not data:
        return None
    return fernet.encrypt(data.encode()).decode()


def decrypt_data(data: str | None) -> str | None:
    if not data:
        return None
    return fernet.decrypt(data.encode()).decode()
