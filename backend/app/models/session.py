from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Session(Base):
    __tablename__ = "awf_sessions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("awf_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    access_token: Mapped[str] = mapped_column(String, nullable=False, index=True)

    login_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    logout_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
