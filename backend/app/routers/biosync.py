"""Bio-Sync endpoints: upload, status, delete of encrypted biomarker data.

Per PRD §5 privacy: all biomarker payloads are AES-256-GCM encrypted at rest.
Decrypted values never leave the request-processing scope.
One Biomarker row per user — upload replaces any existing record.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.middleware.auth import get_current_user
from app.middleware.rate_limit import limiter
from app.models import Biomarker, User
from app.models.base import get_db
from app.schemas.models import BiomarkerStatusResponse, BiomarkerUploadRequest
from app.services.crypto import encrypt_biomarker

router = APIRouter(dependencies=[Depends(get_current_user)])

_BIOMARKER_TTL_DAYS = 180


# ─────────────────────────────────────────────
# POST /biosync/upload
# ─────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=BiomarkerStatusResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
def upload_biomarkers(
    request: Request,
    body: BiomarkerUploadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    ciphertext, iv = encrypt_biomarker(body.data, settings.aes_key)

    existing = db.scalar(select(Biomarker).where(Biomarker.user_id == current_user.id))
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=_BIOMARKER_TTL_DAYS)

    if existing:
        existing.encrypted_data = ciphertext
        existing.encryption_iv = iv
        existing.uploaded_at = now
        existing.expires_at = expires_at
        biomarker = existing
    else:
        biomarker = Biomarker(
            user_id=current_user.id,
            encrypted_data=ciphertext,
            encryption_iv=iv,
            uploaded_at=now,
            expires_at=expires_at,
        )
        db.add(biomarker)

    db.commit()
    db.refresh(biomarker)

    return BiomarkerStatusResponse(
        id=biomarker.id,
        uploaded_at=biomarker.uploaded_at,
        expires_at=biomarker.expires_at,
        has_data=True,
    )


# ─────────────────────────────────────────────
# GET /biosync/status
# ─────────────────────────────────────────────

@router.get("/status", response_model=BiomarkerStatusResponse)
def biomarker_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    biomarker = db.scalar(select(Biomarker).where(Biomarker.user_id == current_user.id))
    if not biomarker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No biomarker data for this user",
        )
    return BiomarkerStatusResponse(
        id=biomarker.id,
        uploaded_at=biomarker.uploaded_at,
        expires_at=biomarker.expires_at,
        has_data=True,
    )


# ─────────────────────────────────────────────
# DELETE /biosync/data
# ─────────────────────────────────────────────

@router.delete("/data", status_code=status.HTTP_204_NO_CONTENT)
def delete_biomarkers(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    biomarker = db.scalar(select(Biomarker).where(Biomarker.user_id == current_user.id))
    if not biomarker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No biomarker data for this user",
        )
    db.delete(biomarker)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
