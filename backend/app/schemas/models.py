from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class SemaphoreColor(str, Enum):
    GRAY = "GRAY"       # Error de lectura / datos insuficientes
    BLUE = "BLUE"       # Ingredientes limpios
    YELLOW = "YELLOW"   # Aditivos bajo observación (EWG/EFSA)
    ORANGE = "ORANGE"   # Conflicto con biomarcadores del usuario
    RED = "RED"         # Toxicidad confirmada / ingrediente prohibido


class ConflictSeverity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ConflictType(str, Enum):
    REGULATORY = "REGULATORY"
    SCIENTIFIC = "SCIENTIFIC"
    TEMPORAL = "TEMPORAL"


class RegulatoryStatus(str, Enum):
    APPROVED = "Approved"
    BANNED = "Banned"
    RESTRICTED = "Restricted"
    UNDER_REVIEW = "Under Review"


# ─────────────────────────────────────────────
# Auth schemas
# ─────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    created_at: datetime


# ─────────────────────────────────────────────
# Scan schemas
# ─────────────────────────────────────────────

class BarcodeRequest(BaseModel):
    barcode: str = Field(min_length=8, max_length=14, pattern=r"^\d+$")


class PhotoScanRequest(BaseModel):
    image_base64: str = Field(description="Base64-encoded image of the ingredient label")


# Structured output schema used with Gemini (§3.A PRD)
class ProductExtraction(BaseModel):
    ingredients: list[str]
    has_additives: bool
    language: str = "es"


class IngredientConflict(BaseModel):
    conflict_type: ConflictType
    severity: ConflictSeverity
    summary: str
    sources: list[str] = Field(description="Regulatory agencies in conflict, e.g. ['FDA', 'EFSA']")


class IngredientResult(BaseModel):
    name: str
    canonical_name: str | None = None
    cas_number: str | None = None
    e_number: str | None = None
    regulatory_status: RegulatoryStatus | None = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    conflicts: list[IngredientConflict] = []


class ScanResponse(BaseModel):
    product_barcode: str
    product_name: str | None = None
    semaphore: SemaphoreColor
    ingredients: list[IngredientResult]
    conflict_severity: ConflictSeverity | None = None
    source: str = Field(description="'barcode' if from OFF, 'photo' if from Gemini OCR")
    scanned_at: datetime


# ─────────────────────────────────────────────
# Biosync schemas
# ─────────────────────────────────────────────

class BiomarkerUploadRequest(BaseModel):
    data: dict = Field(
        description="Raw biomarker data (e.g. blood test results). Encrypted at rest with AES-256."
    )

    @field_validator("data")
    @classmethod
    def data_must_not_be_empty(cls, v: dict) -> dict:
        if not v:
            raise ValueError("Biomarker data cannot be empty")
        return v


class BiomarkerStatusResponse(BaseModel):
    id: UUID
    uploaded_at: datetime
    expires_at: datetime
    has_data: bool = True


class PersonalizedAlert(BaseModel):
    ingredient: str
    biomarker_conflict: str = Field(
        description="Description of conflict between ingredient and user biomarker"
    )
    severity: ConflictSeverity


class BiosyncAnalysis(BaseModel):
    has_biomarkers: bool
    alerts: list[PersonalizedAlert] = []
    semaphore_override: SemaphoreColor | None = Field(
        default=None,
        description="If set, overrides scan semaphore (e.g. ORANGE when biomarker conflict detected)"
    )


# ─────────────────────────────────────────────
# OFF contribution schemas (Fase 2)
# ─────────────────────────────────────────────

class OFFContributeRequest(BaseModel):
    barcode: str = Field(..., min_length=4, max_length=50)
    ingredients: list[str] = Field(..., min_length=1)
    image_base64: str | None = None
    consent: Literal[True] = Field(
        description="Debe ser True — opt-in explícito por escaneo (PRD §9.6)"
    )
    scan_history_id: UUID | None = None


class OFFContributeResponse(BaseModel):
    contribution_id: UUID
    status: Literal["PENDING", "SUBMITTED", "FAILED"]
    message: str
