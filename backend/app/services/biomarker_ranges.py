"""Rangos de referencia canónicos por biomarcador + clasificación.

Cuando el PDF del laboratorio reporta su propio rango (lab_low/lab_high) lo
preferimos. Si no, caemos a la tabla canónica de aquí. La fuente queda
registrada en `Biomarker.reference_source` para que el frontend pueda
indicar visualmente al usuario de dónde viene el rango.

Las fuentes citadas son las guías clínicas que se tomaron como referencia;
no son consejo médico — el sistema sólo distingue normal/alto/bajo para
gatillar la lógica de personalización.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.models import (
    BiomarkerClassification,
    CanonicalBiomarker,
    ReferenceSource,
)


@dataclass(frozen=True)
class RangeSpec:
    low: float
    high: float
    unit: str
    source: str  # guideline name, p.ej. "AHA 2023"


# Rangos canónicos generales para adultos (no diferenciados por sexo/edad).
# Si una agencia mayor revisa estos cortes, actualizar aquí — es data, no
# lógica.
CANONICAL_RANGES: dict[CanonicalBiomarker, RangeSpec] = {
    CanonicalBiomarker.LDL: RangeSpec(0, 100, "mg/dL", "AHA 2023"),
    CanonicalBiomarker.HDL: RangeSpec(40, 200, "mg/dL", "AHA 2023"),
    CanonicalBiomarker.TOTAL_CHOLESTEROL: RangeSpec(0, 200, "mg/dL", "AHA 2023"),
    CanonicalBiomarker.TRIGLYCERIDES: RangeSpec(0, 150, "mg/dL", "AHA 2023"),
    CanonicalBiomarker.GLUCOSE: RangeSpec(70, 99, "mg/dL", "ADA 2024"),
    CanonicalBiomarker.HBA1C: RangeSpec(4.0, 5.6, "%", "ADA 2024"),
    CanonicalBiomarker.SODIUM: RangeSpec(135, 145, "mmol/L", "Mayo Clinic"),
    CanonicalBiomarker.POTASSIUM: RangeSpec(3.5, 5.0, "mmol/L", "Mayo Clinic"),
    CanonicalBiomarker.URIC_ACID: RangeSpec(2.5, 7.0, "mg/dL", "Mayo Clinic"),
    CanonicalBiomarker.CREATININE: RangeSpec(0.6, 1.3, "mg/dL", "Mayo Clinic"),
    CanonicalBiomarker.ALT: RangeSpec(7, 56, "U/L", "AASLD 2023"),
    CanonicalBiomarker.AST: RangeSpec(10, 40, "U/L", "AASLD 2023"),
    CanonicalBiomarker.TSH: RangeSpec(0.4, 4.0, "mIU/L", "ATA 2024"),
    CanonicalBiomarker.VITAMIN_D: RangeSpec(30, 100, "ng/mL", "Endocrine Society"),
    CanonicalBiomarker.IRON: RangeSpec(60, 170, "mcg/dL", "Mayo Clinic"),
    CanonicalBiomarker.FERRITIN: RangeSpec(20, 250, "ng/mL", "Mayo Clinic"),
    CanonicalBiomarker.HEMOGLOBIN: RangeSpec(12.0, 17.5, "g/dL", "WHO"),
    CanonicalBiomarker.HEMATOCRIT: RangeSpec(36.0, 50.0, "%", "WHO"),
    CanonicalBiomarker.PLATELETS: RangeSpec(150, 450, "10^3/uL", "Mayo Clinic"),
    CanonicalBiomarker.WBC: RangeSpec(4.5, 11.0, "10^3/uL", "Mayo Clinic"),
}


def resolve_range(
    name: CanonicalBiomarker,
    lab_low: float | None,
    lab_high: float | None,
) -> tuple[float | None, float | None, ReferenceSource]:
    """Devuelve (low, high, source) preferiendo el rango del lab si está completo."""
    if lab_low is not None and lab_high is not None:
        return lab_low, lab_high, ReferenceSource.LAB

    canonical = CANONICAL_RANGES.get(name)
    if canonical is not None:
        return canonical.low, canonical.high, ReferenceSource.CANONICAL

    return None, None, ReferenceSource.NONE


def classify(
    name: CanonicalBiomarker,
    value: float,
    lab_low: float | None = None,
    lab_high: float | None = None,
) -> tuple[BiomarkerClassification, float | None, float | None, ReferenceSource]:
    """Clasifica un valor como low/normal/high/unknown.

    Returns:
        (classification, range_low_used, range_high_used, source) — donde
        range_low_used/range_high_used son los rangos efectivamente aplicados
        (sea del lab o del fallback canónico) para que el caller los
        persista junto con la clasificación.
    """
    low, high, source = resolve_range(name, lab_low, lab_high)

    if low is None or high is None:
        return BiomarkerClassification.UNKNOWN, low, high, source

    if value < low:
        return BiomarkerClassification.LOW, low, high, source
    if value > high:
        return BiomarkerClassification.HIGH, low, high, source
    return BiomarkerClassification.NORMAL, low, high, source


__all__ = ["CANONICAL_RANGES", "RangeSpec", "classify", "resolve_range"]
