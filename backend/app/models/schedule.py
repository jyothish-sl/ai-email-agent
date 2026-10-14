# app/models/schedule.py
from datetime import datetime, timezone, date, time
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Integer, Date, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Schedule(Base):
    __tablename__ = "awf_schedules"

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

    agent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("awf_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # lazy="selectin" issues one batched follow-up SELECT for all rows in
    # a query result, instead of a lazy per-row load - safe to access on
    # an async session without needing explicit selectinload() at every
    # call site.
    agent = relationship("Agent", lazy="selectin", viewonly=True)

    @property
    def agent_name(self) -> str | None:
        """Exposed so ScheduleResponse can return the agent's display
        name without the frontend having to separately fetch /agents
        and join client-side."""
        return self.agent.name if self.agent else None

    # UI: Schedule Name
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Stored cron expression (built from other fields)
    cron_expression: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # UI: Start Date
    start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    # UI: Start Time
    start_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )

    # UI: Repeat type (once/minutes/hours/days/weeks/months)
    interval_type: Mapped[str] = mapped_column(
        String(20),
        default="minutes",
        nullable=False,
    )

    # UI: Interval value
    interval_value: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )

    timezone: Mapped[str] = mapped_column(
        String(100),
        default="UTC",
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    last_run: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    next_run: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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