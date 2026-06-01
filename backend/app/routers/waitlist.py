"""Waitlist pública para captura de emails pre-launch.

Endpoints públicos (sin JWT). Rate limiting por IP vía slowapi.
Idempotencia via INSERT con manejo de UNIQUE constraint violation.
Turnstile verification server-side para bloquear bots.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.middleware.rate_limit import limiter
from app.models import WaitlistSignup
from app.models.base import get_db

logger = logging.getLogger(__name__)

# Snapshot del texto de consentimiento — versionar si cambia el texto.
CONSENT_TEXT_V1 = (
    "Acepto recibir invitación al beta Q2 2026 y el tratamiento de mis datos "
    "personales conforme a la LFPDPPP de México. Puedo solicitar su eliminación "
    "en cualquier momento a privacy@bioshield.mx."
)

router = APIRouter(prefix="/waitlist", tags=["waitlist"])


class WaitlistSignupIn(BaseModel):
    email: EmailStr
    name: str | None = Field(default=None, max_length=100)
    source: str | None = Field(default=None, max_length=100)
    signup_intent: str | None = Field(default=None, max_length=500)
    consent: bool
    turnstile_token: str


class WaitlistSignupOut(BaseModel):
    position: int
    total: int


async def _verify_turnstile(token: str, remote_ip: str) -> None:
    """Verifica token de Cloudflare Turnstile. Lanza 422 si falla."""
    settings = get_settings()
    secret = settings.turnstile_secret_key

    # En dev (secret == "dev"), skip la verificación para no bloquear tests
    if secret == "dev":
        logger.warning("Turnstile verification skipped (dev mode)")
        return

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": secret, "response": token, "remoteip": remote_ip},
            timeout=5.0,
        )

    result = resp.json()
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "captcha_failed", "message": "Verificación de seguridad falló"},
        )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=WaitlistSignupOut)
@limiter.limit("5/minute")
async def create_signup(
    request: Request,
    body: WaitlistSignupIn,
    db: Session = Depends(get_db),
) -> WaitlistSignupOut:
    # Consentimiento explícito requerido por LFPDPPP
    if not body.consent:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "consent_required", "message": "El consentimiento es obligatorio"},
        )

    remote_ip = request.client.host if request.client else "unknown"
    await _verify_turnstile(body.turnstile_token, remote_ip)

    # Normalizar email a lowercase
    email_lower = body.email.lower()
    expires = datetime.now(UTC) + timedelta(days=365)

    signup = WaitlistSignup(
        id=str(uuid4()),
        email=email_lower,
        name=body.name,
        source=body.source,
        signup_intent=body.signup_intent,
        consent_text=CONSENT_TEXT_V1,
        expires_at=expires,
    )

    try:
        db.add(signup)
        db.flush()
        db.commit()
    except Exception as exc:
        db.rollback()
        # Detectar violación del UNIQUE index (SQLite y PostgreSQL lanzan mensajes distintos)
        exc_str = str(exc).lower()
        if "unique" in exc_str or "duplicate" in exc_str:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "already_registered", "message": "Ya estás en la lista"},
            )
        logger.exception("Waitlist signup error: database operation failed")
        raise

    # Contar total activo para devolver posición
    total: int = db.execute(
        text("SELECT COUNT(*) FROM waitlist_signups WHERE expires_at > :now"),
        {"now": datetime.now(UTC)},
    ).scalar_one()

    return WaitlistSignupOut(position=total, total=total)


@router.get("/count", status_code=status.HTTP_200_OK)
def get_count(db: Session = Depends(get_db)) -> dict:
    """Conteo público del waitlist. El frontend convierte a rangos para evitar mostrar números bajos."""
    total: int = db.execute(
        text("SELECT COUNT(DISTINCT LOWER(email)) FROM waitlist_signups WHERE expires_at > :now"),
        {"now": datetime.now(UTC)},
    ).scalar_one()
    return {"total": total}
