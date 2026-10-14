import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_data, encrypt_data, get_current_user
from app.database.deps import get_db
from app.models.credential import Credential
from app.schemas.credential import (
    PROVIDERS,
    CredentialCreate,
    CredentialOut,
    CredentialUpdate,
    ProviderInfo,
    build_masked_preview,
)

credentials_router = APIRouter()

def _to_out(cred: Credential) -> CredentialOut:
    return CredentialOut(
        id=str(cred.id),
        category=cred.category,
        provider=cred.provider,
        provider_display_name=PROVIDERS[cred.provider]["display_name"],
        model_name=cred.model_name,
        label=cred.label,
        is_active=cred.is_active,
        masked_preview=cred.masked_preview,
        created_at=cred.created_at.isoformat(),
        updated_at=cred.updated_at.isoformat(),
    )

async def _get_owned_credential(
    credential_id: str,
    current_user,
    db: AsyncSession,
) -> Credential:
    result = await db.execute(
        select(Credential).where(
            Credential.id == credential_id,
            Credential.user_id == current_user.id,
        )
    )
    credential = result.scalar_one_or_none()
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )
    return credential

@credentials_router.get("/providers", response_model=list[ProviderInfo])
async def list_providers() -> list[ProviderInfo]:
    return [
        {
            "provider": key,
            "category": spec["category"],
            "display_name": spec["display_name"],
            "fields": spec["fields"],
        }
        for key, spec in PROVIDERS.items()
    ]

@credentials_router.get("", response_model=list[CredentialOut])
async def list_credentials(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CredentialOut]:
    result = await db.execute(
        select(Credential)
        .where(Credential.user_id == current_user.id)
        .order_by(Credential.created_at.desc())
    )
    return [_to_out(c) for c in result.scalars().all()]

@credentials_router.post("", response_model=CredentialOut, status_code=status.HTTP_201_CREATED)
async def create_credential(
    payload: CredentialCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CredentialOut:
    try:
        payload.validate_against_category()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    if payload.category == "llm":
        existing = await db.execute(
            select(Credential).where(
                Credential.user_id == current_user.id,
                Credential.category == "llm",
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have an LLM provider connected. Edit or delete it before adding another.",
            )

    credential = Credential(
        user_id=current_user.id,
        category=payload.category,
        provider=payload.provider,
        model_name=payload.model_name,
        label=payload.label.strip(),
        encrypted_secret=encrypt_data(json.dumps(payload.secret)),
        masked_preview=build_masked_preview(payload.provider, payload.secret),
    )
    db.add(credential)
    await db.commit()
    await db.refresh(credential)
    return _to_out(credential)

@credentials_router.get("/{credential_id}", response_model=CredentialOut)
async def get_credential(
    credential_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CredentialOut:
    credential = await _get_owned_credential(credential_id, current_user, db)
    return _to_out(credential)

@credentials_router.patch("/{credential_id}", response_model=CredentialOut)
async def update_credential(
    credential_id: str,
    payload: CredentialUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CredentialOut:
    credential = await _get_owned_credential(credential_id, current_user, db)

    if payload.label is not None:
        credential.label = payload.label.strip()

    if payload.is_active is not None:
        credential.is_active = payload.is_active

    if payload.model_name is not None:
        credential.model_name = payload.model_name

    if payload.secret is not None:
        existing_secret = json.loads(decrypt_data(credential.encrypted_secret) or "{}")
        merged_secret = {**existing_secret, **payload.secret}
        credential.encrypted_secret = encrypt_data(json.dumps(merged_secret))
        credential.masked_preview = build_masked_preview(credential.provider, merged_secret)

    await db.commit()
    await db.refresh(credential)
    return _to_out(credential)

@credentials_router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    credential = await _get_owned_credential(credential_id, current_user, db)
    await db.delete(credential)
    await db.commit()