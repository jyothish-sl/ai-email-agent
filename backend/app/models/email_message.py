"""
EmailMessage ORM Model

Represents a single email message in the system.
Stores full email metadata, content, headers, and processing state.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base


def utcnow():
    """Helper function to get current UTC time for SQL defaults."""
    return datetime.now(timezone.utc)


# Valid status values for email workflow
STATUSES = ("queued","classified", "read", "automated")


class EmailMessage(Base):
    """
    ORM model for storing email messages.
    
    Tables and Columns:
    - Core identity: id, user_id, message_id
    - Sender/recipient info: sender, from_name, to_email, cc, bcc, reply_to
    - Message content: subject, snippet, body_text, body_html
    - Threading: thread_id, in_reply_to, references
    - Metadata: folder, labels, importance, priority, has_attachments
    - Email flags: is_read, is_starred, is_archived, is_deleted
    - Classification: classification_id, classification_name, classification_confidence, classification_method, classified_at
    - AI processing: ai_summary, ai_keywords, ai_entities, ai_sentiment, processed, processed_at
    - Audit: created_at, updated_at
    
    User Isolation: All queries must filter by user_id to ensure multi-tenancy.
    """

    __tablename__ = "awf_email_messages"

    # ========================================================================
    # Core Identity Fields
    # ========================================================================

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        doc="Unique identifier for this email record (UUID)",
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("awf_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key to awf_users - ensures multi-tenant isolation",
    )

    message_id: Mapped[str | None] = mapped_column(
        String(998),
        nullable=True,
        index=True,
        doc="IMAP/Gmail message identifier - used for deduplication when fetching emails",
    )

    # ========================================================================
    # Sender & Recipient Information
    # ========================================================================

    sender: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        doc="Email address of the sender (always required)",
    )

    from_name: Mapped[str | None] = mapped_column(
        String(255),
        doc="Display name of sender (e.g., 'John Doe' from 'John Doe <john@example.com>')",
    )

    to_email: Mapped[str | None] = mapped_column(
        Text,
        doc="Primary recipient email address(es) - may be comma-separated for multiple recipients",
    )

    cc: Mapped[str | None] = mapped_column(
        Text,
        doc="CC recipients (comma-separated list of email addresses)",
    )

    bcc: Mapped[str | None] = mapped_column(
        Text,
        doc="BCC recipients - typically only visible to the recipient themselves",
    )

    reply_to: Mapped[str | None] = mapped_column(
        String(500),
        doc="Reply-To header - where replies should be directed if different from sender",
    )

    # ========================================================================
    # Message Content
    # ========================================================================

    subject: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="",
        doc="Email subject line",
    )

    snippet: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        doc="Preview excerpt of email body (first ~100-200 chars)",
    )

    body_text: Mapped[str | None] = mapped_column(
        Text,
        doc="Plain text version of the email body",
    )

    body_html: Mapped[str | None] = mapped_column(
        Text,
        doc="HTML version of the email body",
    )

    # ========================================================================
    # Email Threading
    # ========================================================================

    thread_id: Mapped[str | None] = mapped_column(
        String(998),
        index=True,
        doc="Gmail/IMAP thread identifier - groups related messages together",
    )

    in_reply_to: Mapped[str | None] = mapped_column(
        String(998),
        doc="In-Reply-To header - message_id of the email this is replying to",
    )

    references: Mapped[str | None] = mapped_column(
        Text,
        doc="References header - message_ids of earlier messages in the thread",
    )

    # ========================================================================
    # Email Metadata
    # ========================================================================

    folder: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
        doc="IMAP folder name (e.g., 'INBOX', 'Drafts', 'Sent', custom folders)",
    )

    labels: Mapped[list | None] = mapped_column(
        JSON,
        doc="Gmail labels as JSON array - e.g., ['important', 'work']",
    )

    importance: Mapped[str | None] = mapped_column(
        String(20),
        doc="Email importance level: 'high', 'normal', 'low'",
    )

    priority: Mapped[str | None] = mapped_column(
        String(20),
        doc="Email priority level - separate from importance, based on X-Priority header",
    )

    # ========================================================================
    # Attachments
    # ========================================================================

    has_attachments: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Flag indicating whether this email has file attachments",
    )

    attachment_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of attachments in this email",
    )

    # ========================================================================
    # Email Flags / Status Indicators
    # ========================================================================

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="queued",
        index=True,
        doc="Email workflow status: 'queued' (new), 'read' (processed), 'automated' (action taken)",
    )

    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether email has been marked as read in the mailbox",
    )

    is_starred: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether email is starred/flagged for attention",
    )

    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether email has been archived (removed from inbox but not deleted)",
    )

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether email has been marked for deletion (soft delete)",
    )

    # ========================================================================
    # Classification (User-Defined Categories)
    # ========================================================================

    classification_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("awf_email_classify.id", ondelete="SET NULL"),
        index=True,
        doc="Foreign key to EmailClassification - links email to a category",
    )

    classification_name: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
        doc="Cached copy of classification name for quick access without JOIN",
    )

    classification_confidence: Mapped[float | None] = mapped_column(
        Float,
        doc="ML confidence score (0.0-1.0) if using automated classification",
    )

    classification_method: Mapped[str | None] = mapped_column(
        String(30),
        doc="How email was classified: 'keyword' (regex-based), 'llm' (AI model), 'manual' (user)",
    )

    classified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        doc="Timestamp when classification was applied",
    )

    # ========================================================================
    # AI Processing State
    # ========================================================================

    ai_summary: Mapped[str | None] = mapped_column(
        Text,
        doc="AI-generated summary of email content",
    )

    ai_keywords: Mapped[list | None] = mapped_column(
        JSON,
        doc="JSON array of keywords extracted by AI (e.g., ['invoice', 'payment', 'urgent'])",
    )

    ai_entities: Mapped[dict | None] = mapped_column(
        JSON,
        doc="JSON object of named entities extracted by NER (e.g., {'PERSON': ['John'], 'ORG': ['Acme']})",
    )

    ai_sentiment: Mapped[str | None] = mapped_column(
        String(30),
        doc="Sentiment analysis result: 'positive', 'negative', 'neutral', 'mixed'",
    )

    processed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Flag indicating whether this email has been processed by the AI pipeline",
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        doc="Timestamp when AI processing completed",
    )

    # ========================================================================
    # Reply Tracking
    # ========================================================================

    replied: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether a reply has been sent to this email",
    )

    reply_body: Mapped[str | None] = mapped_column(
        Text,
        doc="Full text of the reply sent to this email",
    )

    replied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        doc="Timestamp when reply was sent",
    )

    # ========================================================================
    # Audit Trail
    # ========================================================================

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        doc="When the email was originally received in the mailbox (UTC)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        doc="When this record was created in our system (UTC)",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
        doc="When this record was last modified (UTC) - auto-updated on any change",
    )
