"""
Email Classifications API Endpoints

Manages user-defined email classification categories.
Users can create custom categories and manually classify emails.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database.deps import get_db
from app.models.email_classifications import EmailClassification
from app.schemas.classification import (
    ClassificationCreate,
    ClassificationOut,
    ClassificationUpdate,
)

# Router instance for all classification-related endpoints
classifications_router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================


def _classification_to_out(obj: EmailClassification) -> ClassificationOut:
    """
    Convert an EmailClassification ORM object to response schema.
    
    Uses Pydantic's model_validate for automatic attribute mapping.
    """
    return ClassificationOut.model_validate(obj)


async def _get_classification(
    db: AsyncSession,
    classification_id: UUID,
    user_id: UUID,
) -> EmailClassification:
    """
    Safely retrieve a classification, ensuring ownership.
    
    Args:
        db: AsyncSession for database operations
        classification_id: UUID of the classification to retrieve
        user_id: UUID of the current user (for ownership check)
    
    Returns:
        EmailClassification ORM object
    
    Raises:
        HTTPException 404: If classification doesn't exist or belongs to another user
    """
    result = await db.execute(
        select(EmailClassification).where(
            EmailClassification.id == classification_id,
            EmailClassification.user_id == user_id,
        )
    )
    obj = result.scalar_one_or_none()

    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classification not found",
        )

    return obj


# ============================================================================
# Classification Management Endpoints
# ============================================================================


@classifications_router.get("", response_model=list[ClassificationOut])
async def list_classifications(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[ClassificationOut]:
    """
    Retrieve all classification categories for the current user.
    
    Returns classifications sorted by most recently created first.
    
    Returns:
        List of ClassificationOut objects (user's custom categories)
    """
    result = await db.execute(
        select(EmailClassification)
        .where(EmailClassification.user_id == current_user.id)
        .order_by(EmailClassification.created_at.desc())
    )
    classifications = result.scalars().all()

    return [_classification_to_out(item) for item in classifications]


@classifications_router.post("", response_model=ClassificationOut, status_code=status.HTTP_201_CREATED)
async def create_classification(
    data: ClassificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ClassificationOut:
    """
    Create a new email classification category for the user.
    
    Request Body:
        - name: Display name for the category (e.g., "Invoices", "Support Tickets")
        - prompt: LLM prompt used to identify emails matching this category
        - keywords: List of keywords for regex-based classification fallback
        - enabled: Whether this category is actively used for classification
    
    Returns:
        Created ClassificationOut object with generated ID and timestamps
    """
    obj = EmailClassification(
        user_id=current_user.id,
        **data.model_dump()
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    
    return _classification_to_out(obj)


@classifications_router.get("/{classification_id}", response_model=ClassificationOut)
async def get_classification(
    classification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ClassificationOut:
    """
    Retrieve a single classification by ID.
    
    Path Parameters:
        classification_id: UUID of the classification to retrieve
    
    Returns:
        ClassificationOut object
    """
    obj = await _get_classification(db, classification_id, current_user.id)
    return _classification_to_out(obj)


@classifications_router.put("/{classification_id}", response_model=ClassificationOut)
async def update_classification(
    classification_id: UUID,
    data: ClassificationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ClassificationOut:
    """
    Update an existing classification category.
    
    All fields in the request body are optional. Only provided fields are updated.
    
    Path Parameters:
        classification_id: UUID of the classification to update
    
    Request Body (all optional):
        - name: New display name
        - prompt: New LLM classification prompt
        - keywords: New keyword list for regex classification
        - enabled: Toggle whether this category is active
    
    Returns:
        Updated ClassificationOut object
    """
    obj = await _get_classification(db, classification_id, current_user.id)

    # Extract only the fields that were explicitly provided in the request
    update_data = data.model_dump(exclude_unset=True)

    # If no fields were provided, return unchanged object
    if not update_data:
        return _classification_to_out(obj)

    # Apply provided updates to ORM object
    for field, value in update_data.items():
        setattr(obj, field, value)

    await db.commit()
    await db.refresh(obj)

    return _classification_to_out(obj)


@classifications_router.patch("/{classification_id}", response_model=ClassificationOut)
async def partial_update_classification(
    classification_id: UUID,
    data: ClassificationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ClassificationOut:
    """
    Partially update a classification (alias for PUT).
    
    Provides both PUT and PATCH for API flexibility.
    
    Path Parameters:
        classification_id: UUID of the classification to update
    
    Returns:
        Updated ClassificationOut object
    """
    return await update_classification(classification_id, data, db, current_user)


@classifications_router.delete("/{classification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_classification(
    classification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Delete a classification category.
    
    Note: Emails previously classified with this category will have their
    classification_id set to NULL (due to CASCADE behavior), but the emails
    themselves are preserved.
    
    Path Parameters:
        classification_id: UUID of the classification to delete
    
    Returns:
        204 No Content (successful deletion)
    """
    obj = await _get_classification(db, classification_id, current_user.id)
    await db.delete(obj)
    await db.commit()
