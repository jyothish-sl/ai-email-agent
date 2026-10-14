# app/api/schedule.py
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.deps import get_db
from app.core.security import get_current_user
from app.models.schedule import Schedule
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
)
from app.services import scheduler_service
from app.services.agent_executor import execute_agent, AgentExecutionError

schedule_router = APIRouter()


def build_cron_expression_from_payload(
    start_date,
    start_time,
    interval_type: str,
    interval_value: int,
) -> str:
    minute = start_time.minute if start_time else 0
    hour = start_time.hour if start_time else 0
    interval = interval_value or 1

    if interval_type == "once":
        if not start_date:
            raise ValueError("start_date is required for 'once' schedules")
        return f"{minute} {hour} {start_date.day} {start_date.month} *"

    if interval_type == "minutes":
        return f"*/{interval} * * * *"

    if interval_type == "hours":
        return f"{minute} */{interval} * * *"

    if interval_type == "days":
        return f"{minute} {hour} */{interval} * *"

    if interval_type == "weeks":
        # Display approximation only - see docstring above. Real execution
        # correctly honors "every N weeks" via scheduler_service.
        weekday = start_date.weekday() if start_date else 0  # Mon=0
        cron_weekday = (weekday + 1) % 7  # cron: Sun=0
        return f"{minute} {hour} * * {cron_weekday}"

    if interval_type == "months":
        day = start_date.day if start_date else 1
        return f"{minute} {hour} {day} */{interval} *"

    raise ValueError(f"Unsupported interval_type: {interval_type}")


def _sync_schedule_with_scheduler(schedule: Schedule) -> None:
    """
    Recompute next_run whenever a schedule's timing or enabled state
    changes. There's no separate job store to update anymore - the
    background poll loop in scheduler_service just reads next_run
    straight off this row on its next pass, so "syncing" is just
    "write the correct next_run".
    """
    scheduler_service.recompute_next_run(schedule)


@schedule_router.get("", response_model=list[ScheduleResponse])
async def list_schedules(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Schedule)
        .where(Schedule.user_id == current_user.id)
        .order_by(Schedule.created_at.desc())
    )
    return result.scalars().all()


@schedule_router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    schedule = await db.get(Schedule, schedule_id)

    if not schedule or schedule.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    return schedule


@schedule_router.post(
    "",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule(
    payload: ScheduleCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cron_expression = build_cron_expression_from_payload(
            start_date=payload.start_date,
            start_time=payload.start_time,
            interval_type=payload.interval_type,
            interval_value=payload.interval_value,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    schedule = Schedule(
        user_id=current_user.id,
        agent_id=payload.agent_id,
        name=payload.name,
        cron_expression=cron_expression,
        start_date=payload.start_date,
        start_time=payload.start_time,
        interval_type=payload.interval_type,
        interval_value=payload.interval_value,
        timezone=payload.timezone,
        enabled=payload.enabled,
    )

    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)

    # FIX: creating a Schedule row previously did nothing but write to the
    # DB - nothing ever actually ran it. Now register it with the
    # scheduler (if enabled) and persist the computed next_run time.
    try:
        _sync_schedule_with_scheduler(schedule)
        await db.commit()
        await db.refresh(schedule)
    except ValueError as exc:
        # Trigger couldn't be built (shouldn't normally happen since the
        # schema already validated the interval fields) - roll back the
        # row so we don't leave an orphaned, unschedulable schedule.
        await db.delete(schedule)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return schedule


@schedule_router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: UUID,
    payload: ScheduleUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    schedule = await db.get(Schedule, schedule_id)

    if not schedule or schedule.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    data = payload.model_dump(exclude_unset=True)

    # Recompute cron whenever any field it depends on changes.
    interval_fields = {"start_date", "start_time", "interval_type", "interval_value"}
    timing_changed = bool(interval_fields & data.keys())
    enabled_changed = "enabled" in data

    if timing_changed:
        new_start_date = data.get("start_date", schedule.start_date)
        new_start_time = data.get("start_time", schedule.start_time)
        new_interval_type = data.get("interval_type", schedule.interval_type)
        new_interval_value = data.get("interval_value", schedule.interval_value)

        try:
            data["cron_expression"] = build_cron_expression_from_payload(
                start_date=new_start_date,
                start_time=new_start_time,
                interval_type=new_interval_type,
                interval_value=new_interval_value,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    for key, value in data.items():
        setattr(schedule, key, value)

    # FIX: previously nothing kept the live scheduler in sync with edits -
    # changing the interval on an existing schedule silently did nothing
    # to when it actually ran next.
    if timing_changed or enabled_changed:
        try:
            _sync_schedule_with_scheduler(schedule)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    await db.commit()
    await db.refresh(schedule)

    return schedule


@schedule_router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    schedule = await db.get(Schedule, schedule_id)

    if not schedule or schedule.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    # No separate job store to clean up here - deleting the row is
    # enough, since the poll loop only ever looks at rows that still
    # exist in the table.
    await db.delete(schedule)
    await db.commit()
    return


@schedule_router.patch("/{schedule_id}/toggle")
async def toggle_schedule(
    schedule_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    schedule = await db.get(Schedule, schedule_id)

    if not schedule or schedule.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    schedule.enabled = not schedule.enabled

    # FIX: toggling "enabled" in the DB previously had zero effect on
    # whether the schedule actually ran - now it recomputes next_run
    # (or clears it to None when disabling) so the poll loop picks the
    # change up on its next pass.
    _sync_schedule_with_scheduler(schedule)

    await db.commit()
    await db.refresh(schedule)

    return {"enabled": schedule.enabled, "next_run": schedule.next_run}


@schedule_router.post("/{schedule_id}/run")
async def run_schedule(
    schedule_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    schedule = await db.get(Schedule, schedule_id)

    if not schedule or schedule.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    # FIX: this was a TODO stub. "Run now" is a manual, one-off trigger,
    # so it calls the agent executor directly rather than going through
    # the recurring-job scheduler - it shouldn't affect next_run.
    try:
        await execute_agent(
            agent_id=schedule.agent_id,
            user_id=schedule.user_id,
            db=db,
            schedule_id=schedule.id,
        )
    except AgentExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    schedule.last_run = datetime.utcnow()
    await db.commit()

    return {"message": "Agent execution started"}