"""Bio-Sync endpoints: PDF extraction, upload, status, delete of encrypted biomarker data.

Per PRD §5 privacy: all biomarker payloads are AES-256-GCM encrypted at rest.
Decrypted values never leave the request-processing scope.
One Biomarker row per user — upload replaces any existing record.

POST /biosync/extract does NOT persist — it returns the enriched biomarkers for
the user to review before they confirm via POST /biosync/upload.
"""

import base64
from datetime import UTC, datetime, timedelta
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.middleware.auth import get_current_user
from app.middleware.rate_limit import limiter
from app.models import Biomarker, User
from app.models.base import get_db
from app.schemas.models import (
    BiomarkerExtractionResult,
    BiomarkerStatusResponse,
    BiomarkerUploadRequest,
)
from app.schemas.models import Biomarker as BiomarkerSchema
from app.services.biomarker_ranges import classify
from app.services.crypto import encrypt_biomarker
from app.services.gemini import extract_biomarkers_from_pdf

router = APIRouter(dependencies=[Depends(get_current_user)])

_BIOMARKER_TTL_DAYS = 180
_MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_PDF_PAGES = 5


# ─────────────────────────────────────────────
# POST /biosync/extract  (PDF → biomarkers, no persiste)
# ─────────────────────────────────────────────

@router.post(
    "/extract",
    response_model=BiomarkerExtractionResult,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("10/minute")
async def extract_biomarkers(
    request: Request,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Solo se aceptan archivos PDF (application/pdf)",
        )

    pdf_bytes = await file.read()
    if len(pdf_bytes) > _MAX_PDF_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El PDF excede el límite de {_MAX_PDF_BYTES // (1024 * 1024)} MB",
        )

    pdf_b64 = base64.b64encode(pdf_bytes).decode()
    gemini_result = await extract_biomarkers_from_pdf(pdf_b64, settings)

    enriched: list[BiomarkerSchema] = []
    for extracted in gemini_result.biomarkers:
        classification, range_low, range_high, ref_source = classify(
            extracted.name,
            extracted.value,
            extracted.reference_range_low,
            extracted.reference_range_high,
        )
        enriched.append(
            BiomarkerSchema(
                name=extracted.name,
                raw_name=extracted.raw_name,
                value=extracted.value,
                unit=extracted.unit,
                unit_normalized=extracted.unit_normalized,
                reference_range_low=range_low,
                reference_range_high=range_high,
                reference_source=ref_source,
                classification=classification,
            )
        )

    return BiomarkerExtractionResult(
        biomarkers=enriched,
        lab_name=gemini_result.lab_name,
        test_date=gemini_result.test_date,
        language=gemini_result.language,
    )


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
    payload = body.model_dump(mode="json")
    ciphertext, iv = encrypt_biomarker(payload, settings.aes_key)

    existing = db.scalar(select(Biomarker).where(Biomarker.user_id == current_user.id))
    now = datetime.now(UTC)
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
