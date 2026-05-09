# Security Audit Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mitigar los 2 hallazgos HIGH y 4 ítems defense-in-depth del audit de seguridad 2026-05-09 en una rama aparte de main.

**Architecture:** 7 commits atómicos. Cada commit debe pasar `pytest` completo antes de continuar al siguiente. Los tests que cambian de comportamiento se actualizan en el mismo commit que el código que los rompe. La rama se crea desde main antes de empezar.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, pytest-asyncio, Next.js TypeScript

**Spec:** `docs/superpowers/specs/2026-05-09-security-audit-fixes-design.md`

---

## Setup: Crear rama de trabajo

- [ ] Crear rama desde main:
  ```bash
  git checkout main
  git checkout -b fix/security-audit-2026-05-09
  ```

---

## Task 1: Commit 1 — Vuln 2: Eliminar tokens del body de auth responses

**Objetivo:** `/auth/login` y `/auth/refresh` retornan tokens en body JSON, anulando HttpOnly. Eliminar los tokens del body; dejar solo `expires_in`.

**Files:**
- Modify: `backend/app/schemas/models.py`
- Modify: `backend/app/routers/auth.py`
- Modify: `backend/tests/test_auth.py`
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/lib/api/auth.ts`

- [ ] **Step 1: Actualizar tests PRIMERO (TDD)**

En `backend/tests/test_auth.py`, reemplazar las assertions de body para `test_login_success` (líneas ~83-86):
```python
async def test_login_success(client):
    await client.post(REGISTER_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    response = await client.post(LOGIN_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" not in body
    assert "refresh_token" not in body
    assert "token_type" not in body
    assert "expires_in" in body
    assert body["expires_in"] == 1800  # 30 min * 60
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies
```

Para `test_refresh_issues_new_token_pair` (líneas ~164-176), reemplazar assertions de body:
```python
async def test_refresh_issues_new_token_pair(client):
    await client.post(REGISTER_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    await client.post(LOGIN_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})

    response = await client.post(REFRESH_URL)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" not in body
    assert "refresh_token" not in body
    assert "expires_in" in body
    # New token is valid — can access protected route
    assert "access_token" in response.cookies
    protected = await client.get(PROTECTED_URL)
    assert protected.status_code == 200
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd backend && source .venv/bin/activate
pytest tests/test_auth.py::test_login_success tests/test_auth.py::test_refresh_issues_new_token_pair -v
```
Esperado: FAIL — `assert "access_token" not in body` falla porque el body SÍ contiene el token actualmente.

- [ ] **Step 3: Reemplazar `TokenResponse` en schemas**

En `backend/app/schemas/models.py`, encontrar y reemplazar la clase `TokenResponse`:
```python
# ELIMINAR esto:
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds

# AGREGAR esto en su lugar:
class AuthSuccessResponse(BaseModel):
    expires_in: int  # seconds until access token expires
```

- [ ] **Step 4: Actualizar router de auth**

En `backend/app/routers/auth.py`:

Cambiar el import (línea ~11):
```python
# Antes:
from app.schemas.models import LoginRequest, RegisterRequest, TokenResponse, UserResponse
# Después:
from app.schemas.models import AuthSuccessResponse, LoginRequest, RegisterRequest, UserResponse
```

Cambiar el endpoint `/auth/login` (líneas ~87-110):
```python
@router.post("/login", response_model=AuthSuccessResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access = create_access_token(user.id, settings)
    refresh = create_refresh_token(user.id, settings)
    store_refresh_token(db, user.id, refresh, str(uuid4()), settings)
    db.commit()

    _set_auth_cookies(response, access, refresh, settings)
    return AuthSuccessResponse(expires_in=settings.jwt_access_token_expire_minutes * 60)
```

Cambiar el endpoint `/auth/refresh` (líneas ~118-138):
```python
@router.post("/refresh", response_model=AuthSuccessResponse)
def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    _, new_access, new_refresh = validate_and_rotate_refresh_token(db, refresh_token, settings)
    _set_auth_cookies(response, new_access, new_refresh, settings)
    return AuthSuccessResponse(expires_in=settings.jwt_access_token_expire_minutes * 60)
```

- [ ] **Step 5: Actualizar tipos frontend**

En `frontend/lib/api/types.ts`, reemplazar la interfaz `TokenResponse`:
```typescript
export interface TokenResponse {
  expires_in: number;
}
```
(Mantener el nombre `TokenResponse` — minimiza el diff en `auth.ts`.)

En `frontend/lib/api/auth.ts` no hay cambios necesarios — los tipos de retorno ya apuntan a `TokenResponse` y el interface actualizado propaga automáticamente. Verificar que el archivo no referencia `.access_token` ni `.refresh_token` del resultado de `login()` o `refresh()`.

- [ ] **Step 6: Verificar tests pasan**

```bash
cd backend
pytest tests/test_auth.py -v
```
Esperado: todos los tests de auth en PASS.

```bash
cd frontend
pnpm build
```
Esperado: sin errores de TypeScript.

- [ ] **Step 7: Commit**

```bash
cd ..  # raíz del repo
git add backend/app/schemas/models.py \
        backend/app/routers/auth.py \
        backend/tests/test_auth.py \
        frontend/lib/api/types.ts
git commit -m "fix(auth): remove JWT tokens from response body to preserve HttpOnly"
```

---

## Task 2: Commit 2 — Vuln 1: Strip PHI de result_json + regenerar en lectura

**Objetivo:** `_persist_scan_history` persiste biomarcadores PHI en `result_json` plaintext. Extraer `generate_personalized_insights` como función standalone, strip de insights en escritura, regenerar en lectura desde los biomarcadores cifrados activos del usuario.

**Files:**
- Modify: `backend/app/services/analysis.py` — agregar `generate_personalized_insights` y `_SEVERITY_TO_AVATAR`
- Modify: `backend/app/agents/nodes.py` — `make_personalize_node` delega a la función
- Modify: `backend/app/routers/scan.py` — strip en persist, regenerar en `get_scan_result` y `link_photo_barcode`, ownership check en contribute
- Modify: `backend/app/services/maintenance.py` — agregar `scrub_scan_history_insights`
- Modify: `backend/app/routers/biosync.py` — llamar scrub en DELETE /biosync/data

- [ ] **Step 1: Escribir test para `scrub_scan_history_insights`**

Agregar al final de `backend/tests/test_biosync.py`:
```python
# ─────────────────────────────────────────────
# scrub_scan_history_insights
# ─────────────────────────────────────────────


async def test_delete_scrubs_scan_history_phi(client, db_session, monkeypatch):
    """DELETE /biosync/data debe limpiar personalized_insights de scan_history."""
    import app.services.off_client as off_module
    from app.models import Product, ScanHistory

    await _register(client)
    await client.post(UPLOAD_URL, json=_upload_body())

    # Seed a scan_history row with PHI in result_json
    product = Product(barcode="7501111111111", name="Test", brand=None, image_url=None)
    db_session.add(product)
    db_session.flush()
    scan = ScanHistory(
        user_id=db_session.scalar(
            __import__("sqlalchemy", fromlist=["select"]).select(
                __import__("app.models", fromlist=["User"]).User
            )
        ).id,
        product_barcode="7501111111111",
        semaphore_result="GRAY",
        result_json={
            "product_barcode": "7501111111111",
            "semaphore": "GRAY",
            "ingredients": [],
            "personalized_insights": [{"biomarker_name": "LDL_CHOLESTEROL", "biomarker_value": 130.0}],
        },
    )
    db_session.add(scan)
    db_session.commit()

    response = await client.delete(DELETE_URL)
    assert response.status_code == 204

    db_session.expire_all()
    from sqlalchemy import select as sql_select
    from app.models import ScanHistory as SH
    updated = db_session.scalar(sql_select(SH).where(SH.product_barcode == "7501111111111"))
    assert updated is not None
    assert "personalized_insights" not in (updated.result_json or {})
```

> **Nota:** Este test requiere acceso al `user_id` del usuario registrado. Una forma más limpia es usar la fixture `db_session` para hacer un select del User. Simplificar el seed usando un helper existente en `test_biosync.py` si hay uno, o adaptar el patrón del archivo.

- [ ] **Step 2: Verificar que el test falla**

```bash
cd backend
pytest tests/test_biosync.py::test_delete_scrubs_scan_history_phi -v
```
Esperado: FAIL — `scrub_scan_history_insights` no existe aún.

- [ ] **Step 3: Agregar `generate_personalized_insights` a `services/analysis.py`**

Al principio del archivo `backend/app/services/analysis.py`, agregar `asyncio` y `cast` a los imports si no están:
```python
import asyncio
from typing import TYPE_CHECKING, Literal, cast  # agregar cast si no está
```

Si `PersonalizedInsight` no está en el bloque de imports de `app.schemas.models`, agregarlo:
```python
from app.schemas.models import (
    CanonicalBiomarker,
    ConflictSeverity,
    IngredientResult,
    PersonalizedAlert,
    PersonalizedInsight,   # agregar si no está
    RegulatoryStatus,
    # ... resto de imports existentes
)
```

Agregar la constante y la función al **final** del archivo:
```python
# ─────────────────────────────────────────────
# Standalone personalization — shared by LangGraph node and read-path endpoints
# ─────────────────────────────────────────────

_SEVERITY_TO_AVATAR: dict[str, str] = {
    ConflictSeverity.HIGH.value: "red",
    ConflictSeverity.MEDIUM.value: "orange",
    ConflictSeverity.LOW.value: "yellow",
}


async def generate_personalized_insights(
    resolved: list[IngredientResult],
    biomarkers: list | None,
    settings: "Settings",
) -> list[PersonalizedInsight]:
    """Keyword + semantic matching → Gemini copy → list[PersonalizedInsight].

    Extracted from make_personalize_node so endpoints can call it on read
    without re-running the full LangGraph pipeline.
    Does NOT persist anything — caller decides what to do with the result.
    """
    from app.services import gemini as gemini_service
    from app.services.rag import get_collection

    collection = get_collection(settings)
    matches = await find_ingredient_matches(biomarkers, resolved, settings, collection)
    if not matches:
        return []

    async def _build_insight(
        bm,
        ingr_names: list[str],
        severity: ConflictSeverity,
        kind: str,
        direction: str,
        semantic_score: float = 0.0,
    ) -> PersonalizedInsight:
        name = bm.get("name") if isinstance(bm, dict) else getattr(bm, "name", "")
        value = bm.get("value") if isinstance(bm, dict) else getattr(bm, "value", 0.0)
        unit = bm.get("unit") if isinstance(bm, dict) else getattr(bm, "unit", "")
        classification = (
            bm.get("classification")
            if isinstance(bm, dict)
            else getattr(bm, "classification", "high")
        )
        ref_low = (
            bm.get("reference_range_low")
            if isinstance(bm, dict)
            else getattr(bm, "reference_range_low", None)
        )
        ref_high = (
            bm.get("reference_range_high")
            if isinstance(bm, dict)
            else getattr(bm, "reference_range_high", None)
        )
        name_val = name.value if (name is not None and hasattr(name, "value")) else str(name)
        class_val = (
            classification.value
            if (classification is not None and hasattr(classification, "value"))
            else str(classification)
        )
        float_value = float(value or 0.0)

        copy = await gemini_service.generate_personalized_insight(
            biomarker_name=name_val,
            biomarker_value=float_value,
            biomarker_unit=str(unit),
            classification=class_val,
            severity=severity.value,
            affecting_ingredients=ingr_names,
            kind=kind,
            settings=settings,
        )
        return PersonalizedInsight(
            biomarker_name=cast(CanonicalBiomarker, name_val),
            biomarker_value=float_value,
            biomarker_unit=str(unit),
            classification=cast(Literal["low", "normal", "high"], class_val),
            affecting_ingredients=ingr_names,
            severity=severity,
            kind=cast(Literal["alert", "watch"], kind),
            impact_direction=cast(Literal["raises", "lowers"], direction),
            reference_range_low=ref_low,
            reference_range_high=ref_high,
            friendly_title=copy.friendly_title,
            friendly_biomarker_label=copy.friendly_biomarker_label,
            friendly_explanation=copy.friendly_explanation,
            friendly_recommendation=copy.friendly_recommendation,
            avatar_variant=cast(
                Literal["yellow", "orange", "red"],
                _SEVERITY_TO_AVATAR.get(severity.value, "yellow"),
            ),
        )

    insights = await asyncio.gather(*[_build_insight(*m) for m in matches])
    return list(insights)
```

- [ ] **Step 4: Refactorizar `make_personalize_node` para delegar**

En `backend/app/agents/nodes.py`, reemplazar el cuerpo completo de `make_personalize_node` (líneas ~239-317):
```python
def make_personalize_node(settings: Settings):
    async def node(state: ScanState) -> ScanState:
        from app.services.analysis import generate_personalized_insights

        resolved = state.get("resolved") or []
        biomarkers = state.get("biomarkers")
        insights = await generate_personalized_insights(resolved, biomarkers, settings)
        return {"personalized_insights": insights}

    return node
```

Eliminar también `_SEVERITY_TO_AVATAR` de `nodes.py` (ya vive en `analysis.py`).

- [ ] **Step 5: Strip PHI en `_persist_scan_history`**

En `backend/app/routers/scan.py`, línea ~374:
```python
# Antes:
result_json=response.model_dump(mode="json", exclude={"show_barcode_cta"})
# Después:
result_json=response.model_dump(mode="json", exclude={"show_barcode_cta", "personalized_insights"})
```

- [ ] **Step 6: Agregar `scrub_scan_history_insights` a maintenance.py**

En `backend/app/services/maintenance.py`, agregar imports necesarios:
```python
from sqlalchemy import delete, select  # agregar select
from sqlalchemy.orm.attributes import flag_modified

from app.models import Biomarker, ScanHistory  # agregar ScanHistory
```

Agregar la función al final del archivo:
```python
def scrub_scan_history_insights(db: Session, user_id: str) -> int:
    """Remove personalized_insights from result_json for all scans of a user.

    Does NOT commit — caller controls the transaction.
    Returns the number of rows modified.
    """
    rows = db.scalars(
        select(ScanHistory).where(
            ScanHistory.user_id == user_id,
            ScanHistory.result_json.isnot(None),
        )
    ).all()
    count = 0
    for row in rows:
        if isinstance(row.result_json, dict) and "personalized_insights" in row.result_json:
            row.result_json = {
                k: v for k, v in row.result_json.items() if k != "personalized_insights"
            }
            flag_modified(row, "result_json")
            count += 1
    return count
```

- [ ] **Step 7: Actualizar `delete_biomarkers` en biosync.py**

En `backend/app/routers/biosync.py`, agregar el import:
```python
from app.services.maintenance import scrub_scan_history_insights
```

Reemplazar el handler `delete_biomarkers` (líneas ~185-199):
```python
@router.delete("/data", status_code=status.HTTP_204_NO_CONTENT)
def delete_biomarkers(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scrub_scan_history_insights(db, str(current_user.id))
    biomarker = db.scalar(select(Biomarker).where(Biomarker.user_id == current_user.id))
    if not biomarker:
        db.commit()  # persiste el scrub aunque no haya Biomarker row
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No biomarker data for this user",
        )
    db.delete(biomarker)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 8: Actualizar `get_scan_result` para regenerar insights en lectura**

En `backend/app/routers/scan.py`, agregar imports al bloque de imports del módulo:
```python
from app.models import Biomarker, Ingredient, OFFContribution, Product, ScanHistory, User
from app.services.analysis import generate_personalized_insights
from app.services.crypto import decrypt_biomarker
```

También agregar `get_settings` si no está:
```python
from app.config import Settings, get_settings
```

Reemplazar `get_scan_result` (líneas ~86-106) — cambiar a `async def` y agregar `settings`:
```python
@router.get("/result/{barcode}", response_model=ScanResponse)
async def get_scan_result(
    barcode: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    row = db.scalar(
        select(ScanHistory)
        .where(
            ScanHistory.product_barcode == barcode,
            ScanHistory.user_id == current_user.id,
            ScanHistory.result_json.isnot(None),
        )
        .order_by(ScanHistory.scanned_at.desc())
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan no encontrado.")
    product = db.scalar(select(Product).where(Product.barcode == barcode))
    response = ScanResponse.model_validate(row.result_json)
    response.show_barcode_cta = product.needs_barcode_link if product else False

    # Regenerate personalized insights from encrypted biomarkers (PHI never stored)
    biomarker_row = db.scalar(select(Biomarker).where(Biomarker.user_id == current_user.id))
    if biomarker_row:
        try:
            data = decrypt_biomarker(
                biomarker_row.encrypted_data,
                biomarker_row.encryption_iv,
                settings.aes_key,
            )
            biomarkers = (
                data.get("biomarkers")
                if isinstance(data, dict) and "biomarkers" in data
                else None
            )
        except Exception:
            biomarkers = None
        if biomarkers:
            response.personalized_insights = await generate_personalized_insights(
                response.ingredients, biomarkers, settings
            )

    return response
```

- [ ] **Step 9: Actualizar `link_photo_barcode` para regenerar insights en lectura**

En `backend/app/routers/scan.py`, localizar `link_photo_barcode` (línea ~275). Agregar regeneración de insights antes del `return response`:
```python
    response = ScanResponse.model_validate(history.result_json)
    response.product_barcode = real_product.barcode
    response.show_barcode_cta = False

    # Regenerate personalized insights from encrypted biomarkers (PHI never stored)
    biomarker_row = db.scalar(select(Biomarker).where(Biomarker.user_id == current_user.id))
    if biomarker_row:
        try:
            data = decrypt_biomarker(
                biomarker_row.encrypted_data,
                biomarker_row.encryption_iv,
                settings.aes_key,
            )
            biomarkers = (
                data.get("biomarkers")
                if isinstance(data, dict) and "biomarkers" in data
                else None
            )
        except Exception:
            biomarkers = None
        if biomarkers:
            response.personalized_insights = await generate_personalized_insights(
                response.ingredients, biomarkers, settings
            )

    return response
```

- [ ] **Step 10: Verificar tests pasan**

```bash
cd backend
pytest -v
```
Esperado: todos en PASS. Los tests existentes de biosync (`test_delete_404_when_no_data`, `test_delete_removes_data`) siguen pasando porque el scrub es no-op cuando no hay `personalized_insights` en las filas de test.

- [ ] **Step 11: Commit**

```bash
cd ..
git add backend/app/services/analysis.py \
        backend/app/agents/nodes.py \
        backend/app/routers/scan.py \
        backend/app/services/maintenance.py \
        backend/app/routers/biosync.py \
        backend/tests/test_biosync.py
git commit -m "fix(scan): strip PHI from result_json; regenerate insights on read"
```

---

## Task 3: Commit 3 — Data Migration: scrub PHI de filas existentes

**Objetivo:** Filas ya persistidas en `scan_history.result_json` contienen PHI. Alembic data migration para limpiarlas retroactivamente.

**Files:**
- Create: `backend/alembic/versions/<rev>_scrub_phi_from_scan_history.py`

- [ ] **Step 1: Generar el archivo de migración vacío**

```bash
cd backend && source .venv/bin/activate
alembic revision --rev-id scrub_phi_from_scan_history -m "scrub phi from scan history result_json"
```
Esto crea `backend/alembic/versions/scrub_phi_from_scan_history_<hash>_scrub_phi_from_scan_history.py`. Usar el nombre generado.

- [ ] **Step 2: Editar el archivo de migración**

Abrir el archivo generado. Establecer `down_revision = "518f2aab47ed"` (head actual).

Reemplazar el cuerpo completo de `upgrade()` y `downgrade()`:
```python
"""scrub phi from scan history result_json

Revision ID: scrub_phi_from_scan_history
Revises: 518f2aab47ed
Create Date: 2026-05-09
"""

from __future__ import annotations

import json
from typing import Union

from alembic import op
from sqlalchemy import text

revision: str = "scrub_phi_from_scan_history"
down_revision: Union[str, None] = "518f2aab47ed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    result = bind.execute(
        text("SELECT id, result_json FROM scan_history WHERE result_json IS NOT NULL")
    )
    rows = result.fetchall()

    updated = 0
    for row_id, result_json_raw in rows:
        # SQLite devuelve string; PostgreSQL puede devolver dict
        if isinstance(result_json_raw, str):
            try:
                data = json.loads(result_json_raw)
            except (ValueError, TypeError):
                continue
        elif isinstance(result_json_raw, dict):
            data = result_json_raw
        else:
            continue

        if isinstance(data, dict) and "personalized_insights" in data:
            data.pop("personalized_insights")
            bind.execute(
                text("UPDATE scan_history SET result_json = :json WHERE id = :id"),
                {"json": json.dumps(data), "id": row_id},
            )
            updated += 1

    print(f"\n[migration] Scrubbed personalized_insights from {updated} scan_history rows")


def downgrade() -> None:
    pass  # PHI removal is intentional and irreversible
```

- [ ] **Step 3: Ejecutar la migración en el entorno de dev**

```bash
cd backend && source .venv/bin/activate
alembic upgrade head
```
Esperado: migración ejecutada sin errores. Si hay filas con PHI en la DB de dev, el conteo lo indica.

- [ ] **Step 4: Verificar que pytest sigue pasando**

```bash
pytest -v
```
Nota: los tests usan SQLite en memoria con `Base.metadata.create_all()` — no pasan por Alembic. La migración no afecta los tests.

- [ ] **Step 5: Commit**

```bash
cd ..
git add backend/alembic/versions/
git commit -m "fix(db): data migration — scrub PHI from scan_history.result_json"
```

---

## Task 4: Commit 4 — D1: Secrets Validator en Settings

**Objetivo:** El servidor no debe arrancar con `debug=False` y secrets de desarrollo.

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Escribir el test**

Agregar al final de `backend/tests/test_auth.py` (o crear `backend/tests/test_config.py`):
```python
import pytest
from pydantic import ValidationError
from app.config import Settings


def test_dev_jwt_secret_rejected_in_production():
    with pytest.raises((ValidationError, ValueError)):
        Settings(
            debug=False,
            jwt_secret="dev-secret-change-in-production",
            aes_key="safe-aes-key-32-bytes-xxxxxxxxxxx",
            database_url="sqlite:///./test.db",
        )


def test_dev_aes_key_rejected_in_production():
    with pytest.raises((ValidationError, ValueError)):
        Settings(
            debug=False,
            jwt_secret="safe-jwt-secret-for-testing-only",
            aes_key="dev-aes-key-32-bytes-changethis!",
            database_url="sqlite:///./test.db",
        )


def test_both_safe_secrets_accepted_in_production():
    s = Settings(
        debug=False,
        jwt_secret="safe-jwt-secret-for-testing-only",
        aes_key="safe-aes-key-32-bytes-xxxxxxxxxxx",
        database_url="sqlite:///./test.db",
    )
    assert s.debug is False
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd backend
pytest tests/test_config.py -v
```
Esperado: FAIL — `Settings(debug=False, jwt_secret="dev-secret-...")` actualmente no levanta error.

- [ ] **Step 3: Agregar el validator en `config.py`**

En `backend/app/config.py`, agregar el import de `model_validator`:
```python
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
```

Agregar la constante y el validator dentro de la clase `Settings`, justo después de `allowed_origins`:
```python
    # CORS
    allowed_origins: list[str] = ["http://localhost:3000"]

    _DEV_SECRETS: set[str] = {
        "dev-secret-change-in-production",
        "dev-aes-key-32-bytes-changethis!",
    }

    @model_validator(mode="after")
    def reject_dev_secrets_in_production(self) -> "Settings":
        if not self.debug:
            if self.jwt_secret in self._DEV_SECRETS or self.aes_key in self._DEV_SECRETS:
                raise ValueError(
                    "jwt_secret and aes_key must be overridden when debug=False. "
                    "Set them via environment variables JWT_SECRET and AES_KEY."
                )
        return self
```

> **Nota:** `_DEV_SECRETS` como atributo de clase en un modelo Pydantic puede necesitar ser definido fuera de la clase o como constante de módulo para evitar que Pydantic lo trate como campo. Si Pydantic levanta un error de configuración, moverlo a nivel de módulo:
> ```python
> _DEV_SECRETS = {"dev-secret-change-in-production", "dev-aes-key-32-bytes-changethis!"}
> 
> class Settings(BaseSettings):
>     ...
>     @model_validator(mode="after")
>     def reject_dev_secrets_in_production(self) -> "Settings":
>         if not self.debug:
>             if self.jwt_secret in _DEV_SECRETS or self.aes_key in _DEV_SECRETS:
>                 raise ValueError(...)
>         return self
> ```

- [ ] **Step 4: Verificar tests pasan**

```bash
pytest tests/test_config.py -v
```
Esperado: PASS.

```bash
pytest -v
```
Esperado: todos en PASS. `TEST_SETTINGS` usa `debug=True` → el validator no dispara en tests.

- [ ] **Step 5: Commit**

```bash
cd ..
git add backend/app/config.py backend/tests/test_config.py
git commit -m "fix(config): reject dev placeholder secrets when debug=False"
```

---

## Task 5: Commit 5 — D2: Logout revoca todos los tokens del usuario

**Objetivo:** El refresh cookie no llega a `/auth/logout` por path scoping. Usar access token + revocar todos los tokens del usuario.

**Files:**
- Modify: `backend/app/routers/auth.py`

- [ ] **Step 1: Escribir test**

Agregar a `backend/tests/test_auth.py`:
```python
async def test_logout_revokes_all_sessions(client):
    """After logout, even a manually constructed refresh should fail."""
    await client.post(REGISTER_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    await client.post(LOGIN_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})

    logout_response = await client.post(LOGOUT_URL)
    assert logout_response.status_code == 204

    # Refresh should now fail (token was revoked)
    refresh_response = await client.post(REFRESH_URL)
    assert refresh_response.status_code == 401
```

- [ ] **Step 2: Verificar que el test falla**

```bash
cd backend
pytest tests/test_auth.py::test_logout_revokes_all_sessions -v
```
Esperado: FAIL — actualmente el refresh token no se revoca en logout (por el path cookie bug).

- [ ] **Step 3: Actualizar el endpoint logout**

En `backend/app/routers/auth.py`:

Agregar import de `get_current_user`:
```python
from app.middleware.auth import get_current_user
```

Agregar import de `revoke_all_user_tokens`:
```python
from app.services.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    revoke_all_user_tokens,   # agregar
    revoke_user_token,
    store_refresh_token,
    validate_and_rotate_refresh_token,
    verify_password,
)
```

Reemplazar el handler `logout` completo:
```python
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    revoke_all_user_tokens(db, current_user.id)
    response.delete_cookie(_ACCESS_COOKIE)
    response.delete_cookie(_REFRESH_COOKIE, path="/auth/refresh")
```

- [ ] **Step 4: Verificar todos los tests pasan**

```bash
pytest tests/test_auth.py -v
```
Esperado: todos en PASS incluyendo `test_logout_clears_cookies` (el cliente tiene el cookie de access_token del login previo → `get_current_user` lo lee sin problema).

- [ ] **Step 5: Commit**

```bash
cd ..
git add backend/app/routers/auth.py backend/tests/test_auth.py
git commit -m "fix(auth): logout revokes all user tokens via access token (L1)"
```

---

## Task 6: Commit 6 — D3: Security Headers Middleware

**Objetivo:** Las responses no incluyen headers de seguridad HTTP estándar.

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Escribir test**

Agregar `backend/tests/test_security_headers.py`:
```python
"""Verify security headers are present on all responses."""

import pytest


async def test_security_headers_on_health(client):
    response = await client.get("/health")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("x-xss-protection") == "0"


async def test_hsts_absent_in_debug_mode(client):
    # TEST_SETTINGS has debug=True — HSTS must NOT be set in dev
    response = await client.get("/health")
    assert "strict-transport-security" not in response.headers


async def test_security_headers_on_401(client):
    response = await client.get("/biosync/status")
    assert response.status_code == 401
    assert response.headers.get("x-content-type-options") == "nosniff"
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd backend
pytest tests/test_security_headers.py -v
```
Esperado: FAIL — headers no existen aún.

- [ ] **Step 3: Agregar middleware en `main.py`**

En `backend/app/main.py`, agregar el middleware HTTP después de las declaraciones de `app` y `settings` pero **antes** de los `add_middleware` calls:
```python
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "0"
    if not settings.debug:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

El decorador `@app.middleware("http")` es siempre el wrapper más externo — no hay conflicto con `CORSMiddleware` ni `SlowAPIMiddleware`.

- [ ] **Step 4: Verificar tests pasan**

```bash
pytest tests/test_security_headers.py -v
pytest -v
```
Esperado: todos en PASS.

- [ ] **Step 5: Commit**

```bash
cd ..
git add backend/app/main.py backend/tests/test_security_headers.py
git commit -m "fix(security): add HTTP security headers middleware"
```

---

## Task 7: Commit 7 — D4: Ownership check en /scan/contribute

**Objetivo:** Si `scan_history_id` se provee en el body, verificar que pertenece al usuario autenticado.

**Files:**
- Modify: `backend/app/routers/scan.py`

- [ ] **Step 1: Escribir tests**

Agregar a `backend/tests/test_scan.py`:
```python
from app.models import ScanHistory as SH_Model

CONTRIBUTE_URL = "/scan/contribute"
BARCODE_URL_2 = "/scan/barcode"


async def test_contribute_rejects_unowned_scan_history_id(client, db_session, monkeypatch):
    """contribute debe retornar 403 si scan_history_id no pertenece al usuario."""
    import uuid
    from app.models import Product, ScanHistory

    # Registrar usuario A y B
    await client.post(REGISTER_URL, json={"email": "usera@test.ai", "password": "pass123456"})
    await client.post(REGISTER_URL, json={"email": "userb@test.ai", "password": "pass123456"})

    # Crear un scan_history que pertenece a userb (otro usuario)
    from sqlalchemy import select as sql_select
    from app.models import User
    userb = db_session.scalar(sql_select(User).where(User.email == "userb@test.ai"))

    product = Product(barcode="9991111111111", name="Foreign Product", brand=None, image_url=None)
    db_session.add(product)
    db_session.flush()

    foreign_scan = ScanHistory(
        user_id=userb.id,
        product_barcode="9991111111111",
        semaphore_result="GRAY",
        result_json={"product_barcode": "9991111111111", "semaphore": "GRAY", "ingredients": []},
    )
    db_session.add(foreign_scan)
    db_session.commit()

    # Login como user A
    await client.post("/auth/login", json={"email": "usera@test.ai", "password": "pass123456"})

    response = await client.post(
        CONTRIBUTE_URL,
        json={
            "barcode": "9991111111111",
            "ingredients": ["sugar"],
            "scan_history_id": str(foreign_scan.id),
            "consent": True,
        },
    )
    assert response.status_code == 403


async def test_contribute_accepts_owned_scan_history_id(client, db_session, monkeypatch):
    """contribute debe aceptar scan_history_id del usuario autenticado."""
    from app.models import Product, ScanHistory
    from sqlalchemy import select as sql_select
    from app.models import User

    await client.post(REGISTER_URL, json={"email": "ownera@test.ai", "password": "pass123456"})
    await client.post("/auth/login", json={"email": "ownera@test.ai", "password": "pass123456"})

    user = db_session.scalar(sql_select(User).where(User.email == "ownera@test.ai"))
    product = Product(barcode="8881111111111", name="My Product", brand=None, image_url=None)
    db_session.add(product)
    db_session.flush()
    own_scan = ScanHistory(
        user_id=user.id,
        product_barcode="8881111111111",
        semaphore_result="GRAY",
        result_json={"product_barcode": "8881111111111", "semaphore": "GRAY", "ingredients": []},
    )
    db_session.add(own_scan)
    db_session.commit()

    # Mock OFF contribute para que no haga llamada real
    monkeypatch.setattr(
        "app.services.off_client.contribute_product",
        lambda *a, **kw: None,
    )

    response = await client.post(
        CONTRIBUTE_URL,
        json={
            "barcode": "8881111111111",
            "ingredients": ["sugar"],
            "scan_history_id": str(own_scan.id),
            "consent": True,
        },
    )
    assert response.status_code == 202


async def test_contribute_without_scan_history_id_accepted(client, monkeypatch):
    """scan_history_id es opcional — sin él debe funcionar normalmente."""
    await client.post(REGISTER_URL, json={"email": "noid@test.ai", "password": "pass123456"})
    await client.post("/auth/login", json={"email": "noid@test.ai", "password": "pass123456"})

    monkeypatch.setattr(
        "app.services.off_client.contribute_product",
        lambda *a, **kw: None,
    )

    response = await client.post(
        CONTRIBUTE_URL,
        json={
            "barcode": "0000000000001",
            "ingredients": ["sugar"],
            "consent": True,
        },
    )
    assert response.status_code == 202
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd backend
pytest tests/test_scan.py::test_contribute_rejects_unowned_scan_history_id -v
```
Esperado: FAIL — actualmente el endpoint no verifica ownership.

- [ ] **Step 3: Agregar ownership check en `scan_contribute`**

En `backend/app/routers/scan.py`, dentro de `scan_contribute` (línea ~406), agregar el check antes de crear el `OFFContribution` row:
```python
async def scan_contribute(
    request: Request,
    body: OFFContributeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> OFFContributeResponse:
    if body.scan_history_id is not None:
        owned = db.scalar(
            select(ScanHistory).where(
                ScanHistory.id == str(body.scan_history_id),
                ScanHistory.user_id == current_user.id,
            )
        )
        if owned is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="scan_history_id no pertenece al usuario autenticado",
            )

    ingredients_text = ", ".join(body.ingredients)
    # ... resto del handler sin cambios
```

- [ ] **Step 4: Verificar todos los tests pasan**

```bash
pytest tests/test_scan.py -v
pytest -v
```
Esperado: todos en PASS.

- [ ] **Step 5: Commit**

```bash
cd ..
git add backend/app/routers/scan.py backend/tests/test_scan.py
git commit -m "fix(scan): verify scan_history_id ownership in /scan/contribute"
```

---

## Verificación final

- [ ] **Correr la suite completa una última vez**

```bash
cd backend && pytest -v --tb=short
```
Esperado: 0 fallos.

- [ ] **Verificar typecheck de frontend**

```bash
cd frontend && pnpm build
```
Esperado: 0 errores TypeScript.

- [ ] **Revisar los 7 commits**

```bash
cd ..
git log --oneline fix/security-audit-2026-05-09 ^main
```
Esperado: 7 commits, uno por ítem.

- [ ] **Abrir PR hacia main** — nunca merge directo, siempre PR con review.

---

## Resumen de archivos modificados

| Archivo | Task(s) |
|---------|---------|
| `backend/app/schemas/models.py` | 1 |
| `backend/app/routers/auth.py` | 1, 5 |
| `backend/tests/test_auth.py` | 1, 5 |
| `frontend/lib/api/types.ts` | 1 |
| `backend/app/services/analysis.py` | 2 |
| `backend/app/agents/nodes.py` | 2 |
| `backend/app/routers/scan.py` | 2, 7 |
| `backend/app/services/maintenance.py` | 2 |
| `backend/app/routers/biosync.py` | 2 |
| `backend/tests/test_biosync.py` | 2 |
| `backend/alembic/versions/<rev>_scrub_phi_from_scan_history.py` | 3 |
| `backend/app/config.py` | 4 |
| `backend/tests/test_config.py` | 4 |
| `backend/app/main.py` | 6 |
| `backend/tests/test_security_headers.py` | 6 |
