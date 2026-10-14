from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base

def utcnow():
    return datetime.now(timezone.utc)

class Credential(Base):
    __tablename__ = "awf_credentials"

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

    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    provider: Mapped[str] = mapped_column(String(64), nullable=False)

    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    label: Mapped[str] = mapped_column(String(100), nullable=False)

    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)

    masked_preview: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

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