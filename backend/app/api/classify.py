"""
Email Classification API

Runs the classification LangGraph agent over the user's queued
(unclassified) emails, using their user-defined categories and configured
LLM credential. Mirrors the structure of mail_agents.py's
fetch_and_store_emails so scheduled and manual runs behave identically.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.classify_agent import classify_graph
from app.core.security import get_current_user
from app.database.deps import get_db
from app.models.credential import Credential
from app.models.email_classifications import EmailClassification
from app.models.email_message import EmailMessage
from app.models.llm_usage import LLMUsageLog
from app.services.llm import LLMNotConfigured, decrypt_llm_credential

classify_router = APIRouter()
logger = logging.getLogger("email_agent.classify")

_AGENT_NAME = "email_classification"


def utcnow():
    """Helper function to get current UTC time (matches other model files)."""
    return datetime.now(timezone.utc)


# ============================================================================
# Response Schema
# ============================================================================


class ClassifyResponse(BaseModel):
    """Response schema for the classification run."""

    scanned: int = Field(description="Number of queued emails considered")
    classified: int = Field(description="Number of emails assigned a category")
    skipped: int = Field(description="Number of emails left unclassified (no confident match)")
    llm_calls: int = Field(description="Number of LLM calls made during this run (0 if keyword-only)")
    input_tokens: int = Field(description="Total input/prompt tokens across this run's LLM calls")
    output_tokens: int = Field(description="Total output/completion tokens across this run's LLM calls")


class UsageSummaryResponse(BaseModel):
    """Response schema for aggregate LLM usage totals."""

    agent: Optional[str] = Field(description="Agent filter applied, if any")
    calls: int = Field(description="Total number of LLM calls in the period")
    input_tokens: int = Field(description="Total input/prompt tokens in the period")
    output_tokens: int = Field(description="Total output/completion tokens in the period")
    total_tokens: int = Field(description="input_tokens + output_tokens")


class UsagePoint(BaseModel):
    """One bucket of a usage time series - maps directly to one chart data point."""

    year: int
    month: int
    day: Optional[int] = Field(default=None, description="Omitted when group_by='month'")
    provider: str
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int


class UsageSeriesResponse(BaseModel):
    """Response schema for chart-ready grouped usage data."""

    group_by: str = Field(description="'day' or 'month'")
    points: list[UsagePoint]


# ============================================================================
# Classification Endpoint
# ============================================================================


async def classify_and_store_emails(
    user_id,
    db: AsyncSession,
    limit: int = 50,
) -> ClassifyResponse:
    """
    Classify up to `limit` queued emails for a user against their enabled
    EmailClassification categories, persisting results onto EmailMessage.

    Args:
        user_id: Current user ID (for ownership/isolation)
        db: AsyncSession for database operations
        limit: Max number of queued emails to process in one run

    Returns:
        ClassifyResponse with scanned/classified/skipped counts

    Raises:
        HTTPException 404: If the user has no enabled classification categories
    """
    # Step 1: Load user's enabled categories
    cat_result = await db.execute(
        select(EmailClassification).where(
            EmailClassification.user_id == user_id,
            EmailClassification.enabled == True,  # noqa: E712
        )
    )
    categories = cat_result.scalars().all()

    if not categories:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No enabled classification categories configured. Create at least one first.",
        )

    category_options = [
        {"id": str(c.id), "name": c.name, "prompt": c.prompt, "keywords": c.keywords or []}
        for c in categories
    ]

    # Step 2: Load LLM credential (optional - falls back to keyword-only matching if absent)
    llm_secret: Optional[dict] = None
    cred_result = await db.execute(
        select(Credential).where(
            Credential.user_id == user_id,
            Credential.category == "llm",
            Credential.is_active == True,  # noqa: E712
        )
    )
    llm_credential = cred_result.scalars().first()
    if llm_credential:
        try:
            llm_secret = decrypt_llm_credential(llm_credential)
        except LLMNotConfigured:
            llm_secret = None  # graph will fall back to keyword classification

    # Step 3: Load queued, unclassified emails
    email_result = await db.execute(
        select(EmailMessage)
        .where(
            EmailMessage.user_id == user_id,
            EmailMessage.status == "queued",
            EmailMessage.classification_id.is_(None),
        )
        .limit(limit)
    )
    emails = email_result.scalars().all()

    classified_count = 0
    skipped_count = 0
    llm_call_count = 0
    total_input_tokens = 0
    total_output_tokens = 0

    # Step 4: Run the graph per email and apply results
    for email in emails:
        state = {
            "subject": email.subject,
            "snippet": email.snippet,
            "body_text": email.body_text,
            "sender": email.sender,
            "categories": category_options,
            "llm_credential": llm_secret,
        }
        logger.debug(
            "Classifying email %s (subject=%r, llm_configured=%s)",
            email.id,
            email.subject,
            bool(llm_secret),
        )

        result = await asyncio.to_thread(classify_graph.invoke, state)

        if result.get("error"):
            logger.warning(
                "Classification fallback for email %s: %s (method=%s)",
                email.id,
                result.get("error"),
                result.get("classification_method"),
            )
        logger.debug(
            "Classified email %s -> %s (method=%s, confidence=%s)",
            email.id,
            result.get("classification_name"),
            result.get("classification_method"),
            result.get("classification_confidence"),
        )

        # Log token usage for this call, if the LLM node actually ran
        # (absent entirely on the pure-keyword path, e.g. no LLM credential).
        token_usage = result.get("token_usage")
        if token_usage:
            call_time = utcnow()
            llm_call_count += 1
            input_tokens = token_usage.get("input_tokens") or 0
            output_tokens = token_usage.get("output_tokens") or 0
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens

            db.add(
                LLMUsageLog(
                    user_id=user_id,
                    credential_id=llm_credential.id if llm_credential else None,
                    agent=_AGENT_NAME,
                    provider=(llm_secret or {}).get("provider") or "unknown",
                    model=token_usage.get("model") or "unknown",
                    input_tokens=token_usage.get("input_tokens"),
                    output_tokens=token_usage.get("output_tokens"),
                    total_tokens=token_usage.get("total_tokens"),
                    created_at=call_time,
                    usage_year=call_time.year,
                    usage_month=call_time.month,
                    usage_day=call_time.day,
                )
            )

        if result.get("classification_name"):
            email.classification_id = result["classification_id"]
            email.classification_name = result["classification_name"]
            email.classification_confidence = result["classification_confidence"]
            email.classification_method = result["classification_method"]
            email.classified_at = utcnow()
            email.status = "classified"
            classified_count += 1
        else:
            # No confident match from either LLM or keywords - leave status
            # as "queued" so it can be retried later (e.g. once more
            # categories exist or classification prompts are refined).
            skipped_count += 1

        # Commit after each email rather than once at the end of the whole
        # batch. Each LLM call can take tens of seconds (see the per-call
        # timing in the debug logs above), so a 50-email run can take much
        # longer than a client/proxy is willing to wait. Committing here
        # means that if the request is cancelled or times out partway
        # through, the emails already classified - and the token usage
        # already spent on them - are preserved instead of silently lost
        # and redone from scratch on the next run.
        try:
            await db.commit()
        except Exception:
            logger.exception("Failed to commit classification result for email %s", email.id)
            await db.rollback()

    return ClassifyResponse(
        scanned=len(emails),
        classified=classified_count,
        skipped=skipped_count,
        llm_calls=llm_call_count,
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
    )


@classify_router.post("/classifyEmails", response_model=ClassifyResponse)
async def classify_mail_agent(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClassifyResponse:
    """
    Classify the current user's queued emails into their configured categories.

    This endpoint:
    1. Loads the user's enabled EmailClassification categories
    2. Loads their LLM credential (if any) to enable LLM-based classification
    3. Runs the LangGraph classify agent per email (LLM primary, keyword
       fallback if no LLM credential is configured or the LLM call fails)
    4. Persists classification_id/name/confidence/method + status on match

    Returns:
        ClassifyResponse with counts of scanned/classified/skipped emails

    Raises:
        HTTPException 404: If the user has no enabled classification categories
    """
    return await classify_and_store_emails(current_user.id, db)


@classify_router.get("/llmUsage", response_model=UsageSummaryResponse)
async def get_llm_usage(
    agent: Optional[str] = None,
    since_hours: int = 24 * 30,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageSummaryResponse:
    """
    Return aggregate LLM token usage for the current user.

    Args:
        agent: Optional filter, e.g. "email_classification". Omit for all agents.
        since_hours: How far back to sum usage (default 30 days)

    Returns:
        UsageSummaryResponse with call count and token totals for the period
    """
    from datetime import timedelta

    cutoff = utcnow() - timedelta(hours=since_hours)

    # Sum the real per-row total_tokens where the provider reported it;
    # fall back to input+output only for older rows / providers that never
    # populated total_tokens. Recomputing total purely from input+output
    # (as this endpoint used to) silently zeroes out usage for any call
    # where a provider reported only a total without a token breakdown.
    row_total = func.coalesce(
        LLMUsageLog.total_tokens,
        func.coalesce(LLMUsageLog.input_tokens, 0) + func.coalesce(LLMUsageLog.output_tokens, 0),
    )

    query = select(
        func.count(LLMUsageLog.id),
        func.coalesce(func.sum(LLMUsageLog.input_tokens), 0),
        func.coalesce(func.sum(LLMUsageLog.output_tokens), 0),
        func.coalesce(func.sum(row_total), 0),
    ).where(
        LLMUsageLog.user_id == current_user.id,
        LLMUsageLog.created_at >= cutoff,
    )
    if agent:
        query = query.where(LLMUsageLog.agent == agent)

    result = await db.execute(query)
    call_count, input_tokens, output_tokens, total_tokens = result.one()

    return UsageSummaryResponse(
        agent=agent,
        calls=call_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


@classify_router.get("/llmUsage/series", response_model=UsageSeriesResponse)
async def get_llm_usage_series(
    group_by: str = "day",
    agent: Optional[str] = None,
    since_days: int = 30,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageSeriesResponse:
    """
    Return LLM usage grouped into chart-ready buckets, split by provider and
    model so a dashboard can render one series per model (e.g. a stacked or
    multi-line chart of tokens over time).

    Args:
        group_by: "day" (default) or "month". Groups on the denormalized
            usage_year/usage_month[/usage_day] columns - no date-truncation
            functions needed.
        agent: Optional filter, e.g. "email_classification". Omit for all agents.
        since_days: How many days back to include (default 30)

    Returns:
        UsageSeriesResponse with one UsagePoint per (period, provider, model)
        bucket, ready to feed directly into a chart library

    Raises:
        HTTPException 422: If group_by isn't "day" or "month"
    """
    from datetime import timedelta

    if group_by not in ("day", "month"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="group_by must be 'day' or 'month'",
        )

    cutoff = utcnow() - timedelta(days=since_days)

    group_cols = [LLMUsageLog.usage_year, LLMUsageLog.usage_month]
    if group_by == "day":
        group_cols.append(LLMUsageLog.usage_day)
    group_cols += [LLMUsageLog.provider, LLMUsageLog.model]

    # See get_llm_usage: sum the real total_tokens column (falling back to
    # input+output only when total_tokens itself wasn't recorded) instead
    # of recomputing total purely from the nullable input/output sums.
    row_total = func.coalesce(
        LLMUsageLog.total_tokens,
        func.coalesce(LLMUsageLog.input_tokens, 0) + func.coalesce(LLMUsageLog.output_tokens, 0),
    )

    query = (
        select(
            *group_cols,
            func.count(LLMUsageLog.id),
            func.coalesce(func.sum(LLMUsageLog.input_tokens), 0),
            func.coalesce(func.sum(LLMUsageLog.output_tokens), 0),
            func.coalesce(func.sum(row_total), 0),
        )
        .where(
            LLMUsageLog.user_id == current_user.id,
            LLMUsageLog.created_at >= cutoff,
        )
        .group_by(*group_cols)
        .order_by(*group_cols)
    )
    if agent:
        query = query.where(LLMUsageLog.agent == agent)

    result = await db.execute(query)

    points = []
    for row in result.all():
        if group_by == "day":
            year, month, day, provider, model, calls, input_tokens, output_tokens, total_tokens = row
        else:
            year, month, provider, model, calls, input_tokens, output_tokens, total_tokens = row
            day = None

        points.append(
            UsagePoint(
                year=year,
                month=month,
                day=day,
                provider=provider,
                model=model,
                calls=calls,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )
        )

    return UsageSeriesResponse(group_by=group_by, points=points)
