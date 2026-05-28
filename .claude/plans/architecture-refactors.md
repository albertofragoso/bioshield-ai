# BioShield AI — Architecture Refactor Backlog

> **Last updated:** 2026-05-27  
> **Context:** C1–C5 todos mergeados a main. Main en 320 tests passing.  
> **Deep-review date:** 2026-05-26 — plan incorporates all panel mitigations.

---

## Execution protocol

Each refactor follows the same workflow:
1. `git worktree` on `refactor/<slug>` via `superpowers:using-git-worktrees`
2. Implementation via `superpowers:subagent-driven-development` (spec + code quality review gates)
3. Full CI locally before push (`pytest` — all green)
4. PR → merge → delete worktree + branch → pull main
5. Invoke `/explain-code` at end of session

---

## Global entry gate (run ONCE before any candidate)

```bash
cd backend
source .venv/bin/activate
pytest --cov=app --cov-report=term-missing -q 2>&1 | tail -40
```

**Hard stop:** If `agents/nodes.py`, `services/analysis.py`, or `services/alternatives.py` show < 80% line coverage, write the missing tests first. Add `--cov-fail-under=80` to `pytest.ini` so CI enforces this going forward.

---

## Candidates

### ✅ DONE — Candidate 0: Biomarker keyword corpus

- **Branch:** `refactor/biomarker-rules-extraction` (merged PR #28, 2026-05-26)
- **What:** Extracted `BIOMARKER_RULES` from `analysis.py` → `app/services/biomarker_rules.py`. Fixed silent bug in `alternatives.py` (product name used instead of ingredient list). +11 tests.
- **Result:** 277 tests passing.

---

### ✅ DONE — Candidate 1: Semaphore mapping consolidation

- **Slug:** `refactor/semaphore-consolidation`
- **Effort:** ~45 min
- **Strength:** Strong

**Files touched:**
- `app/services/alternatives.py:39–46` — remove `_semaphore_from_clean_score()`
- `app/services/enrichment.py:14–18` — remove `_semaphore()`
- `app/services/semaphore.py` — NEW
- `tests/test_semaphore.py` — NEW

**Panel mitigation (required step 0 in worktree):**
```bash
diff <(grep -A8 "_semaphore" app/services/alternatives.py) \
     <(grep -A8 "_semaphore" app/services/enrichment.py)
```
If diff is empty → mechanical deduplication, proceed. If non-empty → treat as semantic refactor (needs its own concurrency test); stop and report to user before continuing.

**Solution:**
```python
# app/services/semaphore.py
from app.schemas.models import SemaphoreColor

def semaphore_from_score(score: int) -> SemaphoreColor:
    if score == 0: return SemaphoreColor.BLUE
    if score <= 2: return SemaphoreColor.YELLOW
    if score <= 4: return SemaphoreColor.ORANGE
    return SemaphoreColor.RED
```

**Test spec (parametrized table):**
```python
@pytest.mark.parametrize("score,expected", [
    (0, SemaphoreColor.BLUE),
    (1, SemaphoreColor.YELLOW),
    (2, SemaphoreColor.YELLOW),
    (3, SemaphoreColor.ORANGE),
    (4, SemaphoreColor.ORANGE),
    (5, SemaphoreColor.RED),
    (99, SemaphoreColor.RED),
])
def test_semaphore_from_score(score, expected):
    assert semaphore_from_score(score) == expected
```

---

### ✅ DONE — Candidate 2: Biomarker typed shape

- **Slug:** `refactor/biomarker-typed-shape`
- **Effort:** ~2h
- **Strength:** Strong with contractual test gate

**Files touched:**
- `app/services/biomarker_rules.py` — ADD `DecryptedBiomarker` frozen dataclass + `parse_biomarker_payload()`
- `app/agents/nodes.py:152–175` — call `parse_biomarker_payload()` at decrypt; raise `ValueError` on unrecognized shape
- `app/services/analysis.py:142–150` — remove `isinstance(bm, dict)` guards
- `app/services/alternatives.py:88–100` — remove `isinstance(bm, dict)` guards
- `tests/test_biomarker_rules.py` — ADD 3 contractual tests (see below)

**Panel mitigation — 3 contractual tests required BEFORE PR opens:**

1. `test_decrypt_failure_wrong_key` — seed a `Biomarker` row with valid ciphertext + wrong AES key in settings; run the full graph; assert `biomarkers=None`, `semaphore != None`, exception appears in mocked logger.
2. `test_legacy_flatdict_returns_none` — seed a `Biomarker` row with legacy flat-dict format (`{"ldl": 130}` instead of `{"biomarkers": [...]}`); run the full graph; assert `biomarkers=None`, no exception propagated to the response.
3. `test_biomarker_parse_invalid_shape_raises` — call `parse_biomarker_payload({"unexpected": "shape"})` directly; assert `ValueError` is raised.

**Solution:**
```python
# app/services/biomarker_rules.py (addition)
@dataclass(frozen=True)
class DecryptedBiomarker:
    name: str
    classification: str
    value: float | None = None
    unit: str | None = None

def parse_biomarker_payload(raw: dict) -> list[DecryptedBiomarker]:
    """Raises ValueError on unrecognized shape (including legacy flat-dict)."""
    if "biomarkers" not in raw:
        raise ValueError(f"Unrecognized biomarker payload shape: {list(raw.keys())}")
    return [DecryptedBiomarker(**bm) for bm in raw["biomarkers"]]
```

---

### ✅ DONE — Candidate 3: RegulatoryStatus ranking

- **Slug:** `refactor/priority-rankings`
- **Effort:** ~1.5h
- **Strength:** Worth exploring

**Files touched:**
- `app/core/priorities.py` — NEW
- `app/services/analysis.py:44–55` — remove `_STATUS_RANK`, `_SEVERITY_RANK`
- `app/services/conflicts.py` — remove duplicate ranking dict
- `tests/test_priorities.py` — NEW

**Panel mitigation — semantic audit required BEFORE editing:**
```bash
grep -n "_STATUS_RANK\|_SEVERITY_RANK\|BANNED\|RESTRICTED" \
  app/services/analysis.py app/services/conflicts.py
```
Compare entries side by side. If they differ → document the divergence in a comment in `priorities.py` before consolidating. Do NOT silently merge non-equivalent dicts.

**Solution:**
```python
# app/core/priorities.py
from app.schemas.models import RegulatoryStatus, ConflictSeverity

_STATUS_RANK: dict[RegulatoryStatus, int] = {
    RegulatoryStatus.APPROVED: 0,
    RegulatoryStatus.UNDER_REVIEW: 1,
    RegulatoryStatus.RESTRICTED: 2,
    RegulatoryStatus.BANNED: 3,
}

_SEVERITY_RANK: dict[ConflictSeverity, int] = {
    ConflictSeverity.LOW: 0,
    ConflictSeverity.MEDIUM: 1,
    ConflictSeverity.HIGH: 2,
}

def worst_status(statuses: list[RegulatoryStatus]) -> RegulatoryStatus:
    return max(statuses, key=lambda s: _STATUS_RANK[s])

def worst_severity(severities: list[ConflictSeverity]) -> ConflictSeverity:
    return max(severities, key=lambda s: _SEVERITY_RANK[s])
```

---

### ✅ DONE — Candidate 4: ScanState accumulator

- **Slug:** `refactor/scan-state-accumulator` (merged main 2026-05-27)
- **Tests:** +17 (315 total at merge)

**What shipped:**
- `app/agents/accumulator.py` — `ScanStateAccumulator` dataclass con `apply()` (None-guard + hasattr-guard) y `get()` dict-compat
- `app/routers/scan.py` — `accumulated: dict` eliminado en barcode + photo; todas las actualizaciones pasan por `apply()`
- `app/agents/state.py` — `biomarkers: list[DecryptedBiomarker] | None` (runtime import para LangGraph `get_type_hints()`)
- `backend/CLAUDE.md` — reglas de arquitectura C1–C4 documentadas
- Bugs caught: semaphore coercion guard (`isinstance`), personalize node direct-assignment bypass, dead `_persist_scan_history` removed

---

### ✅ DONE — Candidate 5: Retrieval engine

- **Slug:** `refactor/retrieval-engine` (merged main 2026-05-27)
- **Tests:** +5 (320 total at merge)

**What shipped:**
- `RetrievalResult` dataclass (`hits`, `fallback_used`, `corpus_size`, `embed_ms`) — `hybrid_search()` ahora retorna observabilidad
- `_bm25_cache` module-level + `_get_bm25_corpus()` — corpus se construye una vez y se cachea; doble-build bajo concurrencia es benigno (documentado)
- `invalidate_bm25_cache()` — llamado en `_run_enrich_task` y `_run_off_lookup_task` tras ingesta exitosa
- `nodes.py` — actualizado a `result.hits`
- Lifecycle verificado: `db: Session` → per-request; diseño module-level cache + invalidation (no singleton)

---

### ⚫ Candidate 6: PersonalizedInsight ORM (speculative)

- **Status:** Hold — no product requirement yet.
- **Trigger:** User story "why was my last scan flagged?" or compliance audit requirement.

---

## Execution order

```
Global gate (pytest --cov) → C1 → C2 → C3 → [Prerequisites for C4] → C4 → [Lifecycle check for C5] → C5
```

- C1, C2, C3 are independent and can be executed sequentially with no rebase risk.
- C2 touches `alternatives.py`; C1 also touches `alternatives.py`. Merge C1 before starting C2 worktree.
- C4 and C5 are gated on prerequisite work. Do not start them without completing the verification steps.

## Known pre-existing bugs (discovered during deep review)

### ✅ FIXED
1. **`detect_conflicts_node` in-place mutation** — fixed 2026-05-26 via `model_copy(update=...)`. Test `test_detect_conflicts_node_is_idempotent` added to `test_graph.py`.

### ✅ FIXED (C4)

2. **`ScanState.biomarkers` untyped** — `list[DecryptedBiomarker] | None` desde C4 (2026-05-27). Runtime import (no TYPE_CHECKING) para compatibilidad con LangGraph `get_type_hints()`.
