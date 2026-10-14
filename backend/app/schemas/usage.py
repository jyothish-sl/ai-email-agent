# app/schemas/usage.py
from datetime import date
from pydantic import BaseModel


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
    daily: list[DailyUsage]
    by_provider: list[ProviderUsage]
    by_agent: list[AgentUsage]
    totals: UsageTotals