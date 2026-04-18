"""Map extracted ingredient text to canonical Ingredient rows with a confidence score.

Resolution order (per docs/embedding-strategy.md §6):
  - Exact CAS match       → 1.0
  - Exact E-number match  → 0.95
  - Fuzzy ≥ 85%           → 0.7–0.9
  - Fuzzy 60–85%          → 0.6–0.7 (HITL queue)
  - < 60%                 → None

HITL threshold (0.7) is initial/arbitrary — calibration pending (see
backend/reviews/18-04.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Ingredient

_CAS_RE = re.compile(r"\b(\d{2,7}-\d{2}-\d)\b")
_E_NUMBER_RE = re.compile(r"\b[Ee](\d{3,4}[a-z]?)\b")

HITL_THRESHOLD = 0.7
REJECT_THRESHOLD = 0.6


@dataclass
class Resolution:
    ingredient: Ingredient | None
    confidence: float
    needs_hitl: bool
    matched_on: str  # "cas" | "e_number" | "fuzzy" | "none"


def _scan_cas(text: str) -> str | None:
    match = _CAS_RE.search(text)
    return match.group(1) if match else None


def _scan_e_number(text: str) -> str | None:
    match = _E_NUMBER_RE.search(text)
    return f"E{match.group(1)}" if match else None


def resolve(extracted_name: str, db: Session) -> Resolution:
    """Resolve a single extracted ingredient to a canonical Ingredient row."""
    text = extracted_name.strip()

    # 1. Exact CAS
    cas = _scan_cas(text)
    if cas:
        ing = db.scalar(select(Ingredient).where(Ingredient.cas_number == cas))
        if ing:
            return Resolution(ing, 1.0, needs_hitl=False, matched_on="cas")

    # 2. Exact E-number
    e_num = _scan_e_number(text)
    if e_num:
        ing = db.scalar(select(Ingredient).where(Ingredient.e_number == e_num))
        if ing:
            return Resolution(ing, 0.95, needs_hitl=False, matched_on="e_number")

    # 3. Fuzzy name match against canonical_name + synonyms
    ingredients = list(db.scalars(select(Ingredient)))
    if not ingredients:
        return Resolution(None, 0.0, needs_hitl=False, matched_on="none")

    candidates: dict[str, Ingredient] = {}
    for ing in ingredients:
        candidates[ing.canonical_name.lower()] = ing
        for syn in ing.synonyms or []:
            candidates[syn.lower()] = ing

    best = process.extractOne(text.lower(), candidates.keys(), scorer=fuzz.token_sort_ratio)
    if not best:
        return Resolution(None, 0.0, needs_hitl=False, matched_on="none")

    matched_text, score, _ = best
    confidence = score / 100.0
    if confidence < REJECT_THRESHOLD:
        return Resolution(None, confidence, needs_hitl=False, matched_on="none")

    ing = candidates[matched_text]
    needs_hitl = REJECT_THRESHOLD <= confidence < HITL_THRESHOLD
    return Resolution(ing, confidence, needs_hitl=needs_hitl, matched_on="fuzzy")
