from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.schemas.models import ConflictSeverity, IngredientResult, PersonalizedInsight, SemaphoreColor


@dataclass
class ScanStateAccumulator:
    """Acumulador tipado para actualizaciones parciales de ScanState desde nodos de astream_events."""

    # Origen del escaneo: "barcode" o "photo"
    source: Literal["barcode", "photo"] = "barcode"

    # Datos del producto extraídos por Gemini
    product_name: str | None = None
    product_brand: str | None = None
    product_image_url: str | None = None

    # Ingredientes crudos y resueltos
    extracted_ingredients: list[str] = field(default_factory=list)
    resolved: list[IngredientResult] = field(default_factory=list)

    # Evaluación de riesgo
    semaphore: SemaphoreColor = SemaphoreColor.GRAY
    conflict_severity: ConflictSeverity | None = None

    # Insights personalizados contra biomarcadores del usuario
    personalized_insights: list[PersonalizedInsight] = field(default_factory=list)

    def apply(self, output: dict) -> None:
        """Fusiona valores no-None de un dict de salida de nodo en este acumulador."""
        for key, value in output.items():
            # Solo actualizar atributos conocidos y valores no-None
            if value is not None and hasattr(self, key):
                setattr(self, key, value)

    def get(self, key: str, default=None):
        """Acceso compatible con dict para callers que usan .get()."""
        return getattr(self, key, default)
