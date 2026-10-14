import asyncio
import calendar
import logging
from datetime import datetime, timedelta, date as date_cls, time as time_cls, timezone
from zoneinfo import ZoneInfo
from uuid import UUID

from sqlalchemy import select

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 30

_poll_task: asyncio.Task | None = None


# ─────────────────────────────────────────────────────────────────────────
# next_run computation - the only "scheduling logic" in this file
# ─────────────────────────────────────────────────────────────────────────

def _add_months(dt: datetime, months: int) -> datetime:
    """Add `months` calendar months to dt, clamping the day if the
    target month is shorter (e.g. Jan 31 + 1 month -> Feb 28/29)."""
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def compute_next_run(schedule, after: datetime | None = None) -> datetime | None:
    """
    Compute the next time `schedule` should fire, strictly after `after`
    (defaults to now), respecting the schedule's timezone.
    
    Returns None for a 'once' schedule that has already had its single run.
    
    Args:
        schedule: Schedule model with start_date, start_time, interval_type,
                 interval_value, timezone, enabled
        after: Comparison point (defaults to UTC now). Will be normalized
              to UTC-aware datetime.
    
    Returns:
        next_run as UTC datetime, or None for disabled/past one-off schedules
    """
    # Normalize after to UTC-aware datetime
    if after is None:
        after = datetime.now(timezone.utc)
    elif after.tzinfo is None:
        # Naive datetime assumed to be UTC
        after = after.replace(tzinfo=timezone.utc)
    else:
        # Already timezone-aware, convert to UTC
        after = after.astimezone(timezone.utc)
    
    # Get user's timezone
    try:
        user_tz = ZoneInfo(schedule.timezone or "UTC")
    except KeyError:
        logger.warning("Invalid timezone %s, using UTC", schedule.timezone)
        user_tz = ZoneInfo("UTC")
    
    # Build anchor in user's timezone, then convert to UTC
    start_time = schedule.start_time or time_cls(0, 0)
    
    if schedule.start_date:
        # Combine date + time as naive datetime
        naive_anchor = datetime.combine(schedule.start_date, start_time)
        # Interpret it in the user's timezone (not UTC)
        anchor_in_user_tz = naive_anchor.replace(tzinfo=user_tz)
        # Convert to UTC for internal storage/comparison
        anchor = anchor_in_user_tz.astimezone(timezone.utc)
    else:
        # No start_date: use the current time in UTC as anchor
        anchor = after
    
    itype = schedule.interval_type
    ival = schedule.interval_value or 1
    
    # ───────────────────────────────────────────────────────────────────
    # Handle each interval type
    # ───────────────────────────────────────────────────────────────────
    
    if itype == "once":
        # One-time schedule: return anchor if it's in the future, else None
        return anchor if anchor > after else None
    
    if itype == "months":
        # Step forward one interval at a time until we're past `after`
        # (linear walk is fine since schedules fire max a few times per year)
        next_run = anchor
        while next_run <= after:
            next_run = _add_months(next_run, ival)
        return next_run
    
    # For minutes, hours, days, weeks: use timedelta
    unit_to_delta = {
        "minutes": timedelta(minutes=ival),
        "hours": timedelta(hours=ival),
        "days": timedelta(days=ival),
        "weeks": timedelta(weeks=ival),
    }
    delta = unit_to_delta.get(itype)
    if delta is None:
        raise ValueError(f"Unsupported interval_type: {itype}")
    
    # If anchor is already in the future, it's the next run
    if anchor > after:
        return anchor
    
    # Otherwise, jump forward in whole steps instead of looping
    # (matters for e.g. a "every 5 minutes" schedule that's been enabled
    # but unpolled for a long time)
    steps_elapsed = (after - anchor) // delta
    return anchor + (steps_elapsed + 1) * delta


def recompute_next_run(schedule) -> None:
    """Call this from the API whenever a schedule is created/updated, so
    next_run is always correct without waiting for the next poll."""
    if not schedule.enabled:
        schedule.next_run = None
        return
    schedule.next_run = compute_next_run(schedule)


# ─────────────────────────────────────────────────────────────────────────
# Background polling loop
# ─────────────────────────────────────────────────────────────────────────

async def _run_due_schedules() -> None:
    """Poll database for schedules due to run, execute them, update next_run."""
    from app.database.db import AsyncSessionLocal
    from app.models.schedule import Schedule
    from app.services.agent_executor import execute_agent

    # Use UTC-aware datetime for comparison
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Schedule)
            .where(Schedule.enabled.is_(True))
            .where(Schedule.next_run.is_not(None))
            .where(Schedule.next_run <= now)
            # SKIP LOCKED: if you run this loop in multiple processes/workers,
            # each due row is only picked up by one instance (Postgres feature)
            .with_for_update(skip_locked=True)
        )
        due_schedules = result.scalars().all()

        for schedule in due_schedules:
            logger.info("Running due schedule %s (agent %s)", schedule.id, schedule.agent_id)
            try:
                await execute_agent(
                    agent_id=schedule.agent_id,
                    user_id=schedule.user_id,
                    db=db,
                    schedule_id=schedule.id,
                )
            except Exception:
                logger.exception("Agent execution failed for schedule %s", schedule.id)
                # Don't let one bad agent run kill the poll loop or block
                # other due schedules in this batch

            schedule.last_run = now

            if schedule.interval_type == "once":
                # One-off schedules disable themselves after running so
                # they don't get treated as "due" forever
                schedule.enabled = False
                schedule.next_run = None
            else:
                schedule.next_run = compute_next_run(schedule, after=now)

        if due_schedules:
            await db.commit()


async def _poll_loop() -> None:
    """Infinite loop: poll schedules every POLL_INTERVAL_SECONDS."""
    logger.info("Schedule poll loop started (interval=%ss)", POLL_INTERVAL_SECONDS)
    while True:
        try:
            await _run_due_schedules()
        except Exception:
            logger.exception("Error while polling schedules")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def start() -> None:
    """Call once during FastAPI startup (lifespan)."""
    global _poll_task
    if _poll_task is None or _poll_task.done():
        _poll_task = asyncio.create_task(_poll_loop())


def shutdown() -> None:
    """Call during FastAPI shutdown (lifespan)."""
    global _poll_task
    if _poll_task is not None:
        _poll_task.cancel()
        _poll_task = None