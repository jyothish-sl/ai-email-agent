"""
Mail Agents (Email Fetching) API

Handles fetching emails from configured IMAP credentials
and storing them in the database for processing.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.fetch_agent import fetch_graph
from app.core.security import get_current_user
from app.database.deps import get_db
from app.models.credential import Credential
from app.models.email_message import EmailMessage
from app.services.mailbox import MailboxNotFetchable, imap_config_from_credential

# Router instance for email fetching endpoints
mail_agents_router = APIRouter()


# ============================================================================
# Response Schemas
# ============================================================================


class FetchResponse(BaseModel):
    """
    Response schema for email fetching operation.
    
    Indicates how many emails were fetched and successfully stored.
    """

    fetched: int = Field(description="Total number of new emails found in mailbox")
    stored: int = Field(description="Number of new emails successfully stored (duplicates filtered)")


# ============================================================================
# Helper Functions
# ============================================================================


def _display_email(credential: Credential) -> str | Optional[str]:
    """
    Extract email address from a credential's masked preview.
    
    Handles both 'email' and 'username' fields which may exist depending
    on the credential provider (Gmail uses 'email', IMAP may use 'username').
    
    Args:
        credential: Credential ORM object with masked_preview
    
    Returns:
        Email/username string or None if not present
    """
    preview = credential.masked_preview or {}
    return preview.get("email") or preview.get("username")


async def _get_owned_email_credential(
    credential_id: str,
    user_id,
    db: AsyncSession,
) -> Credential:
    """
    Safely retrieve an email credential, verifying ownership and category.
    
    Args:
        credential_id: ID of the credential to retrieve
        user_id: Current user ID (for ownership check)
        db: AsyncSession for database operations
    
    Returns:
        Credential ORM object
    
    Raises:
        HTTPException 404: If credential doesn't exist or doesn't belong to user
        HTTPException 422: If credential is not an email/SMTP type
    """
    result = await db.execute(
        select(Credential).where(
            Credential.id == credential_id,
            Credential.user_id == user_id,
        )
    )
    credential = result.scalar_one_or_none()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mailbox credential not found",
        )
    
    if credential.category != "email":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That credential is not an email/SMTP credential",
        )
    
    return credential


# ============================================================================
# Email Fetching Endpoints
# ============================================================================


async def fetch_and_store_emails(user_id, db: AsyncSession) -> FetchResponse:
    """
    Fetch emails from the given user's configured email account(s) and
    store any new ones. Shared by both the manual '/getEmails' route and
    the scheduler (app.services.agent_executor), so scheduled runs and
    manual runs behave identically.
    """
    # Step 1: Get user's email credential
    # For now, uses the first (most recently created) email credential
    # TODO: Support multiple email accounts per user with credential_id parameter
    result = await db.execute(
        select(Credential).where(
            Credential.user_id == user_id,
            Credential.category == "email",
        )
    )
    inbox = result.scalars().first()

    if not inbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mailbox credential not found. Please configure an email account first.",
        )

    # Step 2: Parse credential into IMAP config
    try:
        imap_config = imap_config_from_credential(inbox)
    except MailboxNotFetchable as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    # Step 3: Invoke LangGraph agent to fetch emails
    # Runs in thread pool since IMAP operations are blocking
    result = await asyncio.to_thread(fetch_graph.invoke, imap_config)

    # Step 4: Check for errors from the agent
    if result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch emails: {result['error']}",
        )

    new_emails = result.get("new_emails", [])

    # Step 5: Filter duplicates by checking existing message_ids
    # Prevents storing the same email multiple times across fetch runs
    existing_ids: set[str] = set()
    if new_emails:
        candidate_ids = [e["message_id"] for e in new_emails]
        existing = await db.execute(
            select(EmailMessage.message_id).where(
                EmailMessage.message_id.in_(candidate_ids),
            )
        )
        existing_ids = {row[0] for row in existing}

    # Step 6: Store new emails in database
    stored = 0
    for item in new_emails:
        # Skip if this message_id was already stored
        if item["message_id"] in existing_ids:
            continue

        # Create and add EmailMessage ORM object
        email_message = EmailMessage(
            user_id=user_id,
            message_id=item.get("message_id"),
            sender=item.get("sender") or "unknown",
            from_name=item.get("from_name"),
            to_email=item.get("to_email"),
            cc=item.get("cc"),
            bcc=item.get("bcc"),
            reply_to=item.get("reply_to"),
            thread_id=item.get("thread_id"),
            in_reply_to=item.get("in_reply_to"),
            references=item.get("references"),
            subject=item.get("subject") or "",
            snippet=item.get("snippet") or "",
            body_text=item.get("body_text"),
            body_html=item.get("body_html"),
            folder=item.get("folder", "INBOX"),
            labels=item.get("labels"),
            has_attachments=item.get("has_attachments", False),
            attachment_count=item.get("attachment_count", 0),
            status="queued",  # New emails start in queued state
            received_at=item.get("received_at") or datetime.now(timezone.utc),
            is_read=False,
            is_starred=False,
            is_archived=False,
            is_deleted=False,
            processed=False,  # Awaiting AI processing
        )
        db.add(email_message)
        stored += 1

    # Commit all new emails to database
    await db.commit()

    return FetchResponse(fetched=len(new_emails), stored=stored)


@mail_agents_router.post("/getEmails", response_model=FetchResponse)
async def fetch_mail_agent(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FetchResponse:
    """
    Fetch emails from the user's configured email account(s).

    This endpoint:
    1. Finds the user's email credential (IMAP/Gmail)
    2. Connects to the mailbox using IMAP
    3. Fetches new emails using LangGraph fetch agent
    4. Filters out duplicates by message_id
    5. Stores new emails in the database

    Returns:
        FetchResponse with counts of fetched and stored emails

    Raises:
        HTTPException 404: If no email credential configured
        HTTPException 422: If credential can't be used (invalid config)
        HTTPException 502: If email service is unavailable or returns error
    """
    return await fetch_and_store_emails(current_user.id, db)
