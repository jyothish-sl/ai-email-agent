"""
Dashboard Statistics API

Provides aggregated metrics for the user dashboard:
- Email counts by status and configuration status
- LLM token usage stats (daily trend, by provider, by agent)
"""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database.deps import get_db
from app.models.credential import Credential
from app.models.email_message import EmailMessage
from app.models.llm_usage import LLMUsageLog

dashboard_router = APIRouter()


# ============================================================================
# Response Schemas
# ============================================================================


class DashboardStats(BaseModel):
    """
    Dashboard statistics response schema.

    Aggregated metrics about emails and system configuration.
    """

    total_received: int = Field(description="Total number of emails ever received")
    total_read: int = Field(description="Number of emails that have been read/processed")
    total_automated: int = Field(description="Number of emails that triggered automated actions")
    total_queued: int = Field(description="Number of emails waiting to be processed")
    mail_agents_count: int = Field(description="Number of configured email agents/mailboxes")
    llm_connected: bool = Field(description="Whether an LLM provider has been configured")


class DailyUsage(BaseModel):
    date: date
    input_tokens: int
    output_tokens: int
    total_tokens: int
    calls: int


class ProviderUsage(BaseModel):
    provider: str
    total_tokens: int
    calls: int


class AgentUsage(BaseModel):
    agent: str
    total_tokens: int
    calls: int


class UsageTotals(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    calls: int


class UsageStatsResponse(BaseModel):
    """
    LLM token usage response schema.

    Daily trend + breakdowns by provider and agent, all scoped to the
    current user and the requested lookback window.
    """

    daily: list[DailyUsage]
    by_provider: list[ProviderUsage]
    by_agent: list[AgentUsage]
    totals: UsageTotals


# ============================================================================
# Statistics Endpoints
# ============================================================================


@dashboard_router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    """
    Retrieve dashboard statistics for the current user.

    Returns aggregated counts and configuration status for the dashboard.
    All statistics are isolated to the current user.

    Returns:
        DashboardStats object with:
        - total_received: All emails ever fetched
        - total_read: Emails processed/viewed
        - total_automated: Emails with automated actions
        - total_queued: Emails awaiting processing
        - mail_agents_count: Number of connected email accounts
        - llm_connected: Whether an LLM is configured
    """

    async def count_status(status: str | None) -> int:
        """
        Helper function to count emails by status.

        Args:
            status: Email status to filter by (e.g., 'queued', 'read', 'automated').
                   If None, counts all emails.

        Returns:
            Count of emails matching the criteria.
        """
        stmt = (
            select(func.count())
            .select_from(EmailMessage)
            .where(EmailMessage.user_id == current_user.id)
        )
        if status is not None:
            stmt = stmt.where(EmailMessage.status == status)
        result = await db.execute(stmt)
        return result.scalar_one()

    # Fetch email counts by status
    total_received = await count_status(None)
    total_queued = await count_status("queued")
    total_automated = await count_status("automated")

    # Calculate read count: everything except queued
    # (Reading is implied by any action like automation)
    total_read = total_received - total_queued

    # Count configured email credentials (mail agents)
    # Each credential represents a connected mailbox/email account
    email_creds_result = await db.execute(
        select(func.count())
        .select_from(Credential)
        .where(
            Credential.user_id == current_user.id,
            Credential.category == "email",
        )
    )
    mail_agents_count = email_creds_result.scalar_one()

    # Check if an LLM provider has been configured
    llm_result = await db.execute(
        select(func.count())
        .select_from(Credential)
        .where(
            Credential.user_id == current_user.id,
            Credential.category == "llm",
        )
    )
    llm_connected = llm_result.scalar_one() > 0

    return DashboardStats(
        total_received=total_received,
        total_read=total_read,
        total_automated=total_automated,
        total_queued=total_queued,
        mail_agents_count=mail_agents_count,
        llm_connected=llm_connected,
    )


@dashboard_router.get("/usage-stats", response_model=UsageStatsResponse)
async def get_usage_stats(
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageStatsResponse:
    """
    Retrieve LLM token usage statistics for the current user.

    Returns a daily time series plus breakdowns by provider and by agent,
    all scoped to the current user and limited to the last `days` days.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # --- daily trend ---
    daily_stmt = (
        select(
            LLMUsageLog.usage_year,
            LLMUsageLog.usage_month,
            LLMUsageLog.usage_day,
            func.coalesce(func.sum(LLMUsageLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(LLMUsageLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(LLMUsageLog.total_tokens), 0).label("total_tokens"),
            func.count(LLMUsageLog.id).label("calls"),
        )
        .where(LLMUsageLog.user_id == current_user.id, LLMUsageLog.created_at >= since)
        .group_by(LLMUsageLog.usage_year, LLMUsageLog.usage_month, LLMUsageLog.usage_day)
        .order_by(LLMUsageLog.usage_year, LLMUsageLog.usage_month, LLMUsageLog.usage_day)
    )
    daily_rows = (await db.execute(daily_stmt)).all()
    daily = [
        DailyUsage(
            date=datetime(r.usage_year, r.usage_month, r.usage_day).date(),
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            total_tokens=r.total_tokens,
            calls=r.calls,
        )
        for r in daily_rows
    ]

    # --- by provider ---
    provider_stmt = (
        select(
            LLMUsageLog.provider,
            func.coalesce(func.sum(LLMUsageLog.total_tokens), 0).label("total_tokens"),
            func.count(LLMUsageLog.id).label("calls"),
        )
        .where(LLMUsageLog.user_id == current_user.id, LLMUsageLog.created_at >= since)
        .group_by(LLMUsageLog.provider)
        .order_by(func.sum(LLMUsageLog.total_tokens).desc())
    )
    by_provider = [
        ProviderUsage(provider=r.provider, total_tokens=r.total_tokens, calls=r.calls)
        for r in (await db.execute(provider_stmt)).all()
    ]

    # --- by agent ---
    agent_stmt = (
        select(
            LLMUsageLog.agent,
            func.coalesce(func.sum(LLMUsageLog.total_tokens), 0).label("total_tokens"),
            func.count(LLMUsageLog.id).label("calls"),
        )
        .where(LLMUsageLog.user_id == current_user.id, LLMUsageLog.created_at >= since)
        .group_by(LLMUsageLog.agent)
        .order_by(func.sum(LLMUsageLog.total_tokens).desc())
    )
    by_agent = [
        AgentUsage(agent=r.agent, total_tokens=r.total_tokens, calls=r.calls)
        for r in (await db.execute(agent_stmt)).all()
    ]

    totals = UsageTotals(
        input_tokens=sum(d.input_tokens for d in daily),
        output_tokens=sum(d.output_tokens for d in daily),
        total_tokens=sum(d.total_tokens for d in daily),
        calls=sum(d.calls for d in daily),
    )

    return UsageStatsResponse(daily=daily, by_provider=by_provider, by_agent=by_agent, totals=totals)