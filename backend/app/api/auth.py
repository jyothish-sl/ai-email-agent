from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    get_current_user,
    get_current_user_with_token,
    hash_password,
    verify_password,
)
from app.database.deps import get_db
from app.models.session import Session as UserSession
from app.models.user import User
from app.schemas.user import UserLogin, UserRegister

auth_router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@auth_router.get("/")
async def home():
    return {"message": "Hello"}


@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(request: Request, user: UserRegister, db: AsyncSession = Depends(get_db)):
    email = user.email.lower().strip()

    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    new_user = User(
        username=user.username.strip(),
        email=email,
        password=hash_password(user.password),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return {
        "message": "User created",
        "username": new_user.username,
        "email": new_user.email,
        "user_id": str(new_user.id),
    }


@auth_router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, user: UserLogin, db: AsyncSession = Depends(get_db)):
    email = user.email.lower().strip()
    ip_address = request.client.host if request.client else None

    result = await db.execute(select(User).where(User.email == email))
    db_user = result.scalar_one_or_none()

    # Deliberately the same error whether the email doesn't exist or the
    # password is wrong -- distinguishing them lets an attacker enumerate
    # registered emails.
    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not db_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    access_token = create_access_token({"sub": db_user.email})

    db.add(UserSession(user_id=db_user.id, access_token=access_token, ip_address=ip_address))
    await db.commit()

    return {"access_token": access_token, "token_type": "bearer"}


@auth_router.get("/me")
async def me(current_user=Depends(get_current_user)):
    return {
        "user_id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at.isoformat(),
    }


@auth_router.post("/logout")
async def logout(
    current=Depends(get_current_user_with_token),
    db: AsyncSession = Depends(get_db),
):
    current_user, token = current

    # Match on the specific token, not just the user, so logging out one
    # device doesn't silently kill every other active session for that user.
    await db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == current_user.id,
            UserSession.access_token == token,
            UserSession.is_active.is_(True),
        )
        .values(is_active=False, logout_time=datetime.now(timezone.utc))
    )
    await db.commit()
    return {"message": "Logged out successfully"}
