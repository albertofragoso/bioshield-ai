from datetime import date, datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────


class SemaphoreColor(str, Enum):
    GRAY = "GRAY"  # Error de lectura / datos insuficientes
    BLUE = "BLUE"  # Ingredientes limpios
    YELLOW = "YELLOW"  # Aditivos bajo observación (EWG/EFSA)
    ORANGE = "ORANGE"  # Conflicto con biomarcadores del usuario
    RED = "RED"  # Toxicidad confirmada / ingrediente prohibido


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
    personalized_insights: list["PersonalizedInsight"] = []


class ScanHistoryEntry(BaseModel):
    id: str
    product_barcode: str
    product_name: str | None = None
    semaphore: SemaphoreColor
    conflict_severity: ConflictSeverity | None = None
    source: Literal["barcode", "photo"]
    scanned_at: datetime


# ─────────────────────────────────────────────
# Biosync schemas
# ─────────────────────────────────────────────


class CanonicalBiomarker(str, Enum):
    """Taxonomía canónica reconocida.

    Cualquier biomarcador del PDF que no encaje aquí va a OTHER con su raw_name.
    """

    LDL = "ldl"
    HDL = "hdl"
    TOTAL_CHOLESTEROL = "total_cholesterol"
    TRIGLYCERIDES = "triglycerides"
    GLUCOSE = "glucose"
    HBA1C = "hba1c"
    SODIUM = "sodium"
    POTASSIUM = "potassium"
    URIC_ACID = "uric_acid"
    CREATININE = "creatinine"
    ALT = "alt"
    AST = "ast"
    TSH = "tsh"
    VITAMIN_D = "vitamin_d"
    IRON = "iron"
    FERRITIN = "ferritin"
    HEMOGLOBIN = "hemoglobin"
    HEMATOCRIT = "hematocrit"
    PLATELETS = "platelets"
    WBC = "wbc"
    OTHER = "other"


class BiomarkerClassification(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    UNKNOWN = "unknown"


class ReferenceSource(str, Enum):
    LAB = "lab"  # rango leído del PDF
    CANONICAL = "canonical"  # rango fallback (tabla interna)
    NONE = "none"  # sin rango disponible


class ExtractedBiomarker(BaseModel):
    """Biomarcador tal como sale de Gemini al leer el PDF (pre-enriquecimiento)."""

    name: CanonicalBiomarker
    raw_name: str = Field(description="Nombre exacto como aparece en el PDF")
    value: float
    unit: str
    unit_normalized: bool = True
    reference_range_low: float | None = None
    reference_range_high: float | None = None


class GeminiBiomarkerExtraction(BaseModel):
    """Output schema de Gemini para extracción de PDF de laboratorio."""

    biomarkers: list[ExtractedBiomarker]
    lab_name: str | None = None
    test_date: date | None = None
    language: str = "es"


class Biomarker(BaseModel):
    """Biomarcador estructurado tras enriquecer con rangos canónicos + clasificación."""

    name: CanonicalBiomarker
    raw_name: str
    value: float
    unit: str
    unit_normalized: bool = True
    reference_range_low: float | None = None
    reference_range_high: float | None = None
    reference_source: ReferenceSource = ReferenceSource.NONE
    classification: BiomarkerClassification = BiomarkerClassification.UNKNOWN


class BiomarkerExtractionResult(BaseModel):
    """Respuesta de POST /biosync/extract — biomarcadores ya clasificados, sin persistir."""

    biomarkers: list[Biomarker]
    lab_name: str | None = None
    test_date: date | None = None
    language: str = "es"


class BiomarkerUploadRequest(BaseModel):
    """Body de POST /biosync/upload — la lista revisada por el usuario."""

    biomarkers: list[Biomarker] = Field(min_length=1)
    lab_name: str | None = None
    test_date: date | None = None


class BiomarkerStatusResponse(BaseModel):
    id: UUID
    uploaded_at: datetime
    expires_at: datetime
    has_data: bool = True


class PersonalizedInsightCopy(BaseModel):
    """Copy friendly generado por PERSONALIZED_INSIGHT_PROMPT (output de Gemini)."""

    friendly_title: str = Field(description="Título corto, 3-6 palabras")
    friendly_biomarker_label: str = Field(
        description="Etiqueta cotidiana del biomarcador, ej. 'tu colesterol \"malo\"'"
    )
    friendly_explanation: str = Field(
        description="1-2 oraciones conectando biomarcador con ingredientes"
    )
    friendly_recommendation: str = Field(description="1 oración accionable, no prescriptiva")


class PersonalizedInsight(BaseModel):
    """Insight personalizado por biomarcador × ingredientes del producto.

    kind="alert"  → biomarcador ya fuera de rango en la dirección que empuja el aditivo.
    kind="watch"  → biomarcador normal; el aditivo podría sacarlo de rango (predictivo).
    """

    biomarker_name: CanonicalBiomarker
    biomarker_value: float
    biomarker_unit: str
    classification: Literal["low", "normal", "high"]
    affecting_ingredients: list[str]
    severity: ConflictSeverity
    kind: Literal["alert", "watch"] = "alert"
    impact_direction: Literal["raises", "lowers"]
    reference_range_low: float | None = None
    reference_range_high: float | None = None
    friendly_title: str
    friendly_biomarker_label: str
    friendly_explanation: str
    friendly_recommendation: str
    avatar_variant: Literal["yellow", "orange", "red"]


# ─────────────────────────────────────────────
# Legacy biosync schemas (compute_semaphore aún las usa hasta refactor)
# ─────────────────────────────────────────────


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
        description="If set, overrides scan semaphore (e.g. ORANGE when biomarker conflict detected)",
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


# Resolve forward references now that all models in this module are defined.
ScanResponse.model_rebuild()
