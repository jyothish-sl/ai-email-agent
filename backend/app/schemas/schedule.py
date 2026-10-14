# app/schemas/schedule.py
from datetime import datetime, date, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

IntervalType = Literal["once", "minutes", "hours", "days", "weeks", "months"]

# Sane per-unit bounds for interval_value
_INTERVAL_BOUNDS: dict[str, tuple[int, int]] = {
    "minutes": (1, 59),
    "hours": (1, 23),
    "days": (1, 31),
    "weeks": (1, 52),
    "months": (1, 12),
}


class ScheduleBase(BaseModel):
    agent_id: UUID
    name: str = Field(max_length=100)

    start_date: date | None = None
    start_time: time | None = None

    interval_type: IntervalType = "minutes"
    interval_value: int = Field(default=5, ge=1)

    timezone: str = Field(default="UTC", max_length=100)
    enabled: bool = True

    @model_validator(mode="after")
    def _validate_interval(self):
        if self.interval_type == "once" and self.start_date is None:
            raise ValueError("start_date is required when interval_type is 'once'")

        if self.interval_type in ("hours", "days", "weeks", "months") and self.start_time is None:
            raise ValueError(f"start_time is required when interval_type is '{self.interval_type}'")

        bounds = _INTERVAL_BOUNDS.get(self.interval_type)
        if bounds and not (bounds[0] <= self.interval_value <= bounds[1]):
            raise ValueError(
                f"interval_value must be between {bounds[0]} and {bounds[1]} "
                f"for interval_type '{self.interval_type}'"
            )
        return self


class ScheduleCreate(ScheduleBase):
    # cron_expression is server-computed on create — not accepted from the client.
    pass


class ScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)

    start_date: date | None = None
    start_time: time | None = None

    interval_type: IntervalType | None = None
    interval_value: int | None = Field(default=None, ge=1)

    timezone: str | None = Field(default=None, max_length=100)
    enabled: bool | None = None

    # Note: no client-settable cron_expression here either — it's always
    # derived server-side from the interval fields to avoid drift.


class ScheduleResponse(BaseModel):
    id: UUID
    user_id: UUID
    agent_id: UUID
    agent_name: str | None = None
    name: str
    cron_expression: str

    start_date: date | None
    start_time: time | None

    interval_type: str
    interval_value: int

    timezone: str
    enabled: bool
    last_run: datetime | None
    next_run: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True