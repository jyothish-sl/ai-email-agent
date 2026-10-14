"""
Email Classification Schemas

Pydantic models for classification category CRUD operations.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ClassificationBase(BaseModel):
    """
    Base schema with common fields for all classification schemas.
    
    Defines the core properties that make up a classification category.
    """

    name: str = Field(
        min_length=1,
        max_length=100,
        description="Display name for this classification category (e.g., 'Invoices', 'Support')",
    )
    
    prompt: str = Field(
        min_length=1,
        max_length=2000,
        description="LLM prompt used to identify emails matching this category. "
                    "Should clearly describe what emails belong here.",
    )
    
    keywords: list[str] = Field(
        default_factory=list,
        description="List of keywords for regex-based classification fallback. "
                    "Used when LLM classification is unavailable or disabled.",
    )
    
    enabled: bool = Field(
        default=True,
        description="Whether this classification is active and should be applied to incoming emails",
    )


class ClassificationCreate(ClassificationBase):
    """
    Request schema for creating a new classification.
    
    All fields from ClassificationBase are required except keywords (optional).
    """
    pass


class ClassificationUpdate(BaseModel):
    """
    Request schema for updating an existing classification.
    
    All fields are optional - only provided fields will be updated.
    This allows partial updates (e.g., change only the prompt, keep keywords).
    """

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="New display name (optional)",
    )
    
    prompt: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=2000,
        description="New LLM prompt (optional)",
    )
    
    keywords: Optional[list[str]] = Field(
        default=None,
        description="New keyword list (optional)",
    )
    
    enabled: Optional[bool] = Field(
        default=None,
        description="Toggle active status (optional)",
    )


class ClassificationOut(ClassificationBase):
    """
    Response schema for classification objects (in GET/POST/PUT responses).
    
    Extends ClassificationBase with the database-generated fields
    (ID, user_id, timestamps).
    """

    id: UUID = Field(description="Unique identifier for this classification")
    
    user_id: UUID = Field(description="ID of the user who owns this classification")
    
    created_at: datetime = Field(description="When this classification was created (UTC)")
    
    updated_at: datetime = Field(description="When this classification was last modified (UTC)")

    class Config:
        """
        Pydantic configuration.
        
        from_attributes=True allows automatic mapping from SQLAlchemy ORM objects
        using their attributes (e.g., obj.id, obj.name) during model_validate().
        """
        from_attributes = True
