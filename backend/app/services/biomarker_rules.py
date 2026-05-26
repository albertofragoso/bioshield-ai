"""Canonical biomarker-ingredient conflict rules.

Single source of truth for BiomarkerRule, BIOMARKER_RULES, and keyword constants.
Follows the same pattern as biomarker_ranges.py — data lives here, logic elsewhere.

Extending coverage is a data-curation task: add/edit rules here, no code changes needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.schemas.models import (
    CanonicalBiomarker,
    ConflictSeverity,
)

__all__ = ["BiomarkerRule", "BIOMARKER_RULES", "keywords_for", "excludes_for"]


@dataclass(frozen=True)
class BiomarkerRule:
    biomarker: CanonicalBiomarker
    direction: Literal["raises", "lowers"]  # effect of the ingredient on this biomarker
    keywords: tuple[str, ...]  # substrings to look for in ingredient names (lowercase)
    severity: ConflictSeverity
    message: str
    excludes: tuple[str, ...] = ()  # substrings that disqualify a keyword match
    # Firing logic (derived from direction):
    #   raises → alert when classification=="high", watch when "normal"
    #   lowers → alert when classification=="low",  watch when "normal"


_LIPID_RAISING_KEYWORDS = (
    "trans fat",
    "grasas trans",
    "aceite hidrogenado",
    "hydrogenated",
    "saturated fat",
    "palm oil",
    "aceite de palma",
)

_INDUSTRIAL_HYDROGENATED_EXCLUDES = (
    "petroleum",
    "resin",
    "polymer",
    "copolymer",
    "homopolymer",
    "mw:",
    "decene",
    "dodecene",
    "octene",
    "hexene",
)


# Data-curated rules. Add entries here to extend coverage — no code changes needed.
BIOMARKER_RULES: tuple[BiomarkerRule, ...] = (
    BiomarkerRule(
        biomarker=CanonicalBiomarker.LDL,
        direction="raises",
        keywords=_LIPID_RAISING_KEYWORDS,
        excludes=_INDUSTRIAL_HYDROGENATED_EXCLUDES,
        severity=ConflictSeverity.HIGH,
        message="LDL con grasa trans/saturada",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.TOTAL_CHOLESTEROL,
        direction="raises",
        keywords=_LIPID_RAISING_KEYWORDS,
        excludes=_INDUSTRIAL_HYDROGENATED_EXCLUDES,
        severity=ConflictSeverity.HIGH,
        message="Colesterol total con grasa trans/saturada",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.HDL,
        direction="lowers",
        keywords=("trans fat", "grasas trans", "hydrogenated", "aceite hidrogenado"),
        excludes=_INDUSTRIAL_HYDROGENATED_EXCLUDES,
        severity=ConflictSeverity.MEDIUM,
        message="HDL con grasas trans",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.GLUCOSE,
        direction="raises",
        keywords=(
            "dextrose",
            "dextrosa",
            "maltose",
            "maltosa",
            "refined sugar",
            "white sugar",
            "azúcar refinada",
            "glucose syrup",
            "jarabe de glucosa",
            "high fructose",
            "corn syrup",
        ),
        severity=ConflictSeverity.HIGH,
        message="Glucosa con azúcares de absorción rápida",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.HBA1C,
        direction="raises",
        keywords=(
            "high fructose",
            "corn syrup",
            "jarabe de maíz",
            "fructose",
            "fructosa",
            "added sugar",
            "azúcar añadida",
        ),
        severity=ConflictSeverity.HIGH,
        message="HbA1c con azúcares de carga crónica",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.TRIGLYCERIDES,
        direction="raises",
        keywords=("fructose", "fructosa", "jarabe", "syrup", "added sugar"),
        severity=ConflictSeverity.MEDIUM,
        message="Triglicéridos con fructosa/jarabes",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.SODIUM,
        direction="raises",
        keywords=(
            "sodium chloride",
            "cloruro de sodio",
            "monosodium glutamate",
            "glutamato monosódico",
            "msg",
            "added salt",
            "sal de mesa",
            "table salt",
            "sodium",
            "sodio",
        ),
        excludes=(
            "potassium salt",
            "calcium salt",
            "magnesium salt",
            "fatty acid salt",
            "sodium bicarbonate",
            "sodium carbonate",
            "sodium silicate",
        ),
        severity=ConflictSeverity.MEDIUM,
        message="Sodio con ingredientes salinos",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.URIC_ACID,
        direction="raises",
        keywords=(
            "high fructose",
            "corn syrup",
            "fructose",
            "fructosa",
            "jarabe de maíz",
        ),
        severity=ConflictSeverity.MEDIUM,
        message="Ácido úrico con fructosa",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.POTASSIUM,
        direction="raises",
        keywords=(
            "potassium chloride",
            "cloruro de potasio",
            "potassium",
            "potasio",
            "potásico",
            "kcl",
            "dipotassium",
            "potassic",
        ),
        severity=ConflictSeverity.LOW,
        message="Potasio con aditivos de potasio",
    ),
)


def keywords_for(biomarker_name: str) -> tuple[str, ...]:
    """All keywords across all rules for a given biomarker name (deduped)."""
    seen: set[str] = set()
    result: list[str] = []
    for rule in BIOMARKER_RULES:
        if rule.biomarker.value == biomarker_name:
            for kw in rule.keywords:
                if kw not in seen:
                    seen.add(kw)
                    result.append(kw)
    return tuple(result)


def excludes_for(biomarker_name: str) -> tuple[str, ...]:
    """All excludes across all rules for a given biomarker name (deduped)."""
    seen: set[str] = set()
    result: list[str] = []
    for rule in BIOMARKER_RULES:
        if rule.biomarker.value == biomarker_name:
            for ex in rule.excludes:
                if ex not in seen:
                    seen.add(ex)
                    result.append(ex)
    return tuple(result)
