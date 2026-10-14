# app/models/agent.py
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Agent(Base):
    __tablename__ = "awf_agents"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    endpoint: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    method: Mapped[str] = mapped_column(
        String(10),
        default="POST",
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )