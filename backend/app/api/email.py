"""
Email Management API Endpoints

Handles email retrieval, status updates, manual classification, and replies.
All operations are user-scoped through the email's user_id foreign key.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database.deps import get_db
from app.models.email_classifications import EmailClassification
from app.models.email_message import EmailMessage
from app.schemas.email import (
    ClassifyRequest,
    EmailDetail,
    EmailListItem,
    ReplyRequest,
    ReplyResponse,
    StatusUpdateRequest,
)

# Router instance for all email-related endpoints
emails_router = APIRouter()

# ============================================================================
# Helper Functions for Response Serialization
# ============================================================================


def _to_list_item(email: EmailMessage) -> EmailListItem:
    """
    Convert an EmailMessage ORM object to a list view response.
    
    Used in email listing endpoints. Contains only essential fields needed
    for the UI table/list view (id, sender, subject, snippet, status, etc.).
    """
    return EmailListItem(
        id=email.id,
        sender=email.sender,
        subject=email.subject,
        snippet=email.snippet,
        status=email.status,
        replied=getattr(email, "replied", False),
        classification_id=getattr(email, "classification_id", None),
        received_at=email.received_at,
    )


def _to_detail(email: EmailMessage) -> EmailDetail:
    """
    Convert an EmailMessage ORM object to a full detail response.
    
    Used in detail/modal view endpoints. Includes all available fields
    including body_text, body_html, reply information, etc.
    """
    return EmailDetail(
        id=email.id,
        sender=email.sender,
        recipient=email.to_email,  # Map to_email to recipient in response
        cc=email.cc,
        bcc=email.bcc,
        subject=email.subject,
        snippet=email.snippet,
        body_text=email.body_text,
        body_html=email.body_html,
        status=email.status,
        replied=getattr(email, "replied", False),
        reply_body=getattr(email, "reply_body", None),
        replied_at=getattr(email, "replied_at", None),
        classification_id=email.classification_id,
        received_at=email.received_at,
    )


# ============================================================================
# Email Retrieval Endpoints
# ============================================================================


@emails_router.get("/emails", response_model=list[EmailListItem])
async def list_emails(
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    replied: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[EmailListItem]:
    """
    Retrieve a paginated list of emails for the current user.
    
    Query Parameters:
    - search: Case-insensitive substring search in sender and subject
    - status: Filter by email status (queued, read, automated)
    - replied: Filter by whether email has been replied to
    
    Returns emails sorted by most recent first.
    """
    # Build query: start with filtering by current user
    stmt = select(EmailMessage).where(EmailMessage.user_id == current_user.id)

    # Apply status filter if provided
    if status_filter:
        stmt = stmt.where(EmailMessage.status == status_filter)

    # Apply replied filter if provided
    if replied is not None:
        stmt = stmt.where(EmailMessage.replied == replied)

    # Apply search filter across sender and subject fields
    if search:
        like_pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                EmailMessage.sender.ilike(like_pattern),
                EmailMessage.subject.ilike(like_pattern),
            )
        )

    # Sort by most recent emails first
    stmt = stmt.order_by(EmailMessage.received_at.desc())

    result = await db.execute(stmt)
    emails = result.scalars().all()
    
    return [_to_list_item(e) for e in emails]


@emails_router.get("/emails/{email_id}", response_model=EmailDetail)
async def get_email(
    email_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> EmailDetail:
    """
    Retrieve full details of a specific email by ID.
    
    Includes complete body, headers, and all metadata. Only accessible
    to the email's owner.
    """
    email = await _get_owned_email(db, email_id, current_user.id)
    return _to_detail(email)


# ============================================================================
# Email Status Management Endpoints
# ============================================================================


@emails_router.post("/emails/{email_id}/read", response_model=EmailListItem)
async def mark_email_read(
    email_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> EmailListItem:
    """
    Mark an email as read.
    
    Transitions email from 'queued' to 'read' status. No-op if already read.
    """
    email = await _get_owned_email(db, email_id, current_user.id)

    # Only transition if currently queued
    if email.status == "queued":
        email.status = "read"
        await db.commit()
        await db.refresh(email)

    return _to_list_item(email)


@emails_router.patch("/emails/{email_id}/status", response_model=EmailListItem)
async def update_email_status(
    email_id: UUID,
    payload: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> EmailListItem:
    """
    Update the status of an email.
    
    Allowed statuses: queued, read, automated
    """
    email = await _get_owned_email(db, email_id, current_user.id)
    email.status = payload.status
    await db.commit()
    await db.refresh(email)
    
    return _to_list_item(email)


# ============================================================================
# Email Classification Endpoints
# ============================================================================


@emails_router.patch("/emails/{email_id}/classify", response_model=EmailListItem)
async def classify_email(
    email_id: UUID,
    payload: ClassifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> EmailListItem:
    """
    Manually classify an email under a user-defined category.
    
    Updates the email's classification_id, classification_name, and
    classification_method to 'manual', recording the timestamp.
    """
    # Verify email ownership and existence
    email = await _get_owned_email(db, email_id, current_user.id)

    # Fetch the target classification, ensuring it belongs to the user
    result = await db.execute(
        select(EmailClassification).where(
            EmailClassification.id == payload.classification_id,
            EmailClassification.user_id == current_user.id,
        )
    )
    classification = result.scalar_one_or_none()

    if not classification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classification not found",
        )

    # Update email with classification metadata
    email.classification_id = classification.id
    email.classification_name = classification.name
    email.classification_method = "manual"  # Indicates user-assigned classification
    email.classified_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(email)

    return _to_list_item(email)


# ============================================================================
# Email Reply Endpoints
# ============================================================================


@emails_router.post("/emails/{email_id}/reply", response_model=ReplyResponse)
async def reply_to_email(
    email_id: UUID,
    payload: ReplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ReplyResponse:
    """
    Record a reply to an email.
    
    Stores the reply text and marks the email as replied. Does NOT send
    the email (would require SMTP integration via credentials).
    
    Future: Integrate with email credentials to actually send replies.
    """
    email = await _get_owned_email(db, email_id, current_user.id)

    # Record reply metadata
    email.replied = True
    email.reply_body = payload.body
    email.replied_at = datetime.now(timezone.utc)
    
    # Transition from queued to read if not already
    if email.status == "queued":
        email.status = "read"

    await db.commit()
    await db.refresh(email)

    return ReplyResponse(
        id=email.id,
        replied=email.replied,
        reply_body=email.reply_body,
        replied_at=email.replied_at,
    )


# ============================================================================
# Helper Functions - Access Control
# ============================================================================


async def _get_owned_email(
    db: AsyncSession, email_id: UUID, user_id: UUID
) -> EmailMessage:
    """
    Safely retrieve an email, ensuring the current user is the owner.
    
    Raises HTTPException 404 if email doesn't exist or doesn't belong
    to the specified user.
    """
    stmt = select(EmailMessage).where(
        EmailMessage.id == email_id,
        EmailMessage.user_id == user_id,
    )
    result = await db.execute(stmt)
    email = result.scalar_one_or_none()

    if email is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found",
        )

    return email
