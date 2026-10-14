# app/schemas/agent.py
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentBase(BaseModel):
    name: str = Field(max_length=100)
    code: str = Field(max_length=100)
    description: str | None = None
    category: str = Field(max_length=50)
    endpoint: str = Field(max_length=255)
    method: str = Field(max_length=10, default="POST")
    enabled: bool = True


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    category: str | None = Field(default=None, max_length=50)
    endpoint: str | None = Field(default=None, max_length=255)
    method: str | None = Field(default=None, max_length=10)
    enabled: bool | None = None


class AgentResponse(BaseModel):
    id: UUID
    name: str
    code: str
    description: str | None
    category: str
    endpoint: str
    method: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # (Pydantic v2; use orm_mode=True in v1)