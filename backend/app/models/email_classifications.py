"""
EmailClassification ORM Model

Represents a user-defined email classification category.
Used to organize and categorize emails (e.g., "Invoices", "Support Tickets").
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base


def utcnow():
    """Helper function to get current UTC time for SQL defaults."""
    return datetime.now(timezone.utc)


class EmailClassification(Base):
    """
    ORM model for email classification categories.
    
    Represents a user-defined category for organizing emails.
    Each classification has a name, LLM prompt for identification,
    and keyword list for fallback regex matching.
    
    Columns:
    - id: Unique identifier
    - user_id: Foreign key to owning user (multi-tenant isolation)
    - name: Display name (e.g., "Invoices", "Support Tickets")
    - prompt: LLM prompt for identifying matching emails
    - keywords: JSON list of keywords for regex-based classification
    - enabled: Whether this category is active
    - created_at: Creation timestamp
    - updated_at: Last modification timestamp
    
    Relationships:
    - EmailMessage.classification_id -> EmailClassification.id (cascade to NULL on delete)
    """

    __tablename__ = "awf_email_classify"

    # ========================================================================
    # Identity Fields
    # ========================================================================

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        doc="Unique identifier for this classification category (UUID)",
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("awf_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key to awf_users - ensures multi-tenant isolation and cascade delete",
    )

    # ========================================================================
    # Classification Metadata
    # ========================================================================

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Display name for this classification category (e.g., 'Invoices', 'Support Tickets')",
    )

    prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="LLM prompt used to identify emails belonging to this category. "
            "Used by AI classification pipeline. Example: 'Emails about payment processing, invoices, billing'",
    )

    # ========================================================================
    # Classification Rules
    # ========================================================================

    keywords: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        doc="JSON list of keywords for regex-based classification fallback. "
            "Used when LLM classification is unavailable or disabled. "
            "Example: ['invoice', 'payment due', 'billing', 'statement']",
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Whether this classification is active and should be applied during email processing",
    )

    # ========================================================================
    # Audit Trail
    # ========================================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        doc="When this classification was created (UTC)",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
        doc="When this classification was last modified (UTC) - auto-updated on any change",
    )
