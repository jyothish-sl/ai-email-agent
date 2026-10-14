"""
Email Response Schemas

Pydantic models for serializing email data to API responses.
Separates between list view (EmailListItem) and detail view (EmailDetail).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EmailListItem(BaseModel):
    """
    Schema for email rows in list/table view.
    
    Contains only essential fields for efficient rendering in UI lists.
    Includes: sender, subject, snippet (preview), status, classification reference.
    """

    id: UUID = Field(description="Unique email identifier")
    sender: str = Field(description="Email address of the sender")
    subject: str = Field(description="Email subject line")
    snippet: str = Field(description="Preview/excerpt of email body")
    status: str = Field(description="Email status: queued, read, or automated")
    replied: bool = Field(default=False, description="Whether this email has been replied to")
    classification_id: UUID | None = Field(
        default=None, description="Reference to assigned classification category"
    )
    received_at: datetime = Field(description="When the email was received (UTC)")


class EmailDetail(BaseModel):
    """
    Schema for full email details in modal/detail view.
    
    Complete email including full body text/HTML, all headers (cc, bcc, etc.),
    reply information, and classification metadata.
    """

    id: UUID = Field(description="Unique email identifier")
    sender: str = Field(description="Email address of the sender")
    recipient: str | None = Field(
        default=None, description="Primary recipient email address(es)"
    )
    cc: str | None = Field(default=None, description="CC recipients (comma-separated)")
    bcc: str | None = Field(default=None, description="BCC recipients (comma-separated)")
    subject: str = Field(description="Email subject line")
    snippet: str = Field(description="Preview/excerpt of email body")
    body_text: str | None = Field(
        default=None, description="Plain text version of email body"
    )
    body_html: str | None = Field(
        default=None, description="HTML version of email body"
    )
    status: str = Field(description="Email status: queued, read, or automated")
    replied: bool = Field(default=False, description="Whether this email has been replied to")
    reply_body: str | None = Field(
        default=None, description="Content of the reply sent to this email"
    )
    replied_at: datetime | None = Field(
        default=None, description="Timestamp when reply was sent (UTC)"
    )
    classification_id: UUID | None = Field(
        default=None, description="Reference to assigned classification category"
    )
    received_at: datetime = Field(description="When the email was received (UTC)")


class StatusUpdateRequest(BaseModel):
    """
    Request schema for updating email status.
    
    Allowed values: "queued", "read", "automated"
    This enum prevents invalid status values from being persisted.
    """

    status: str = Field(
        pattern="^(queued|read|automated)$",
        description="Target status: one of queued, read, automated",
    )


class ClassifyRequest(BaseModel):
    """
    Request schema for manually classifying an email.
    
    Assigns the email to a user-defined classification category.
    The classification_id must reference a category owned by the current user.
    """

    classification_id: UUID | None = Field(
        description="ID of the classification category to assign to this email"
    )


class ReplyRequest(BaseModel):
    """
    Request schema for recording a reply to an email.
    
    Note: Only records the reply locally. Actual SMTP sending requires
    integration with email credentials and mail service.
    """

    body: str = Field(
        min_length=1,
        max_length=20000,
        description="Reply text content",
    )


class ReplyResponse(BaseModel):
    """
    Response schema confirming a reply has been recorded.
    
    Returns the stored reply metadata for confirmation to the client.
    """

    id: UUID = Field(description="ID of the email that was replied to")
    replied: bool = Field(description="Confirmation that reply flag is set")
    reply_body: str = Field(description="The reply text that was stored")
    replied_at: datetime = Field(description="Timestamp of reply (UTC)")
