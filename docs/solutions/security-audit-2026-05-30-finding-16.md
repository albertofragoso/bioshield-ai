---
module: scan
tags: [security, audit, assert, production]
problem_type: deferred-finding
---

# Security Audit 2026-05-30 — Finding #16

## Estado

**Cerrado** — resuelto en commit de production readiness 2026-06-26.

## Hallazgo original

El PR `ee5cae18` (fix(security): remediation audit 2026-05-30) cerró 15 de 16 findings.
El finding #16 no fue documentado explícitamente en el PR.

Tras análisis de los gaps subsistentes post-PR, el finding más probable es:

**`assert scan.share_expires_at is not None` en `backend/app/routers/scan.py`** (entonces línea ~770).

- `assert` statements en Python se deshabilitan con la flag `-O` (optimize).
- Si el assert es una guarda real de invariante (que sí lo era), usar `if/raise HTTPException` es el patrón correcto.
- Representa una vulnerabilidad de error handling: en modo optimizado, el código continuaría con `share_expires_at = None` y potencialmente retornaría datos inconsistentes.

## Solución aplicada

```python
# Antes (assert deshabilitable):
assert scan.share_expires_at is not None

# Después (guarda robusta):
if scan.share_expires_at is None:
    raise HTTPException(status_code=500, detail="internal_error")
```

**Archivo:** `backend/app/routers/scan.py` función `create_share_link`.

## Nota

Si el finding #16 original era diferente (e.g., JWT RS256 migration, MFA, RLS en PostgreSQL),
esas mitigaciones están trackadas en el plan de production readiness como S3-3 (RLS) y backlog.
