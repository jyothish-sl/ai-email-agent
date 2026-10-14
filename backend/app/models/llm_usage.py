"""
LLMUsageLog ORM Model

One row per LLM call made by any agent (classification, future agents,
etc.), so token usage can be monitored/summed per user, per provider, per
agent, or over time — independent of which feature triggered the call.

year/month/day are stored alongside created_at (denormalized on write) so
dashboard charts can GROUP BY them directly without date-truncation
functions in every query.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base


def utcnow():
    """Helper function to get current UTC time for SQL defaults."""
    return datetime.now(timezone.utc)


class LLMUsageLog(Base):
    """
    ORM model for logging a single LLM call's token usage.

    Columns:
    - id: Unique identifier
    - user_id: Foreign key to owning user (multi-tenant isolation)
    - credential_id: Which "llm" Credential was used (nullable - credential
      may since have been deleted; kept as SET NULL so history survives)
    - agent: Which agent/feature made the call, e.g. "email_classification"
    - provider: LLM name - "anthropic" | "openai" | "ollama"
    - model: Model name/tag actually used, e.g. "claude-sonnet-4-6", "llama3.1"
    - input_tokens / output_tokens / total_tokens: From the model's
      usage_metadata. May be null if the provider doesn't report usage
      (some local Ollama models/versions don't).
    - created_at: Full UTC timestamp the call was made
    - usage_year / usage_month / usage_day: Denormalized UTC date parts of
      created_at, indexed together, so dashboard charts can group by
      day/month/year directly instead of computing date truncation in SQL
      on every query.
    """

    __tablename__ = "awf_llm_usage_log"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        doc="Unique identifier for this usage log row (UUID)",
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("awf_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key to awf_users - ensures multi-tenant isolation",
    )

    credential_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("awf_credentials.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Which LLM Credential was used for this call, if still present",
    )

    agent: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Which agent/feature made this call, e.g. 'email_classification'",
    )

    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        doc="LLM name/provider used: 'anthropic', 'openai', 'ollama', etc.",
    )

    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Model name/tag actually used, e.g. 'claude-sonnet-4-6', 'llama3.1'",
    )

    input_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Prompt/input tokens for this call, if reported by the provider",
    )

    output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Completion/output tokens for this call, if reported by the provider",
    )

    total_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="input_tokens + output_tokens, if both were reported",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        index=True,
        doc="Full UTC timestamp this call was made",
    )

    # ========================================================================
    # Denormalized date parts (for dashboard charting)
    # ========================================================================
    # Written once at insert time from created_at (UTC). A composite index
    # covers the common "trend chart per user over a period" query shape:
    # WHERE user_id = ? AND usage_year = ? [AND usage_month = ?] GROUP BY ...

    usage_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        doc="UTC year this call was made, e.g. 2026",
    )

    usage_month: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        index=True,
        doc="UTC month this call was made, 1-12",
    )

    usage_day: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        index=True,
        doc="UTC day-of-month this call was made, 1-31",
    )
