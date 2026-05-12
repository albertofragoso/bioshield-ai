# Security Audit Fixes — Design Spec

*Fecha:* 2026-05-09
*Auditoría base:* docs/reviews/09-05.md
*Alcance:* 2 hallazgos HIGH + 4 ítems defense-in-depth
*Branch:* rama aparte de main (nunca merge directo)
*Estrategia de commits:* un commit atómico por vulnerabilidad/ítem

---

## Resumen de cambios

| Commit | Área | Severidad |
|--------|------|-----------|
| 1 | Vuln 2 — Eliminar tokens del body de auth responses | HIGH |
| 2 | Vuln 1 — Strip PHI de result_json en escritura + regenerar en lectura | HIGH |
| 3 | Vuln 1 — Data migration: scrub PHI de filas existentes | HIGH |
| 4 | D1 — Validator de secrets en Settings | Defense-in-depth |
| 5 | D2 — Logout revoca todos los tokens del usuario (L1) | Defense-in-depth |
| 6 | D3 — Security headers middleware | Defense-in-depth |
| 7 | D4 — Ownership check en /scan/contribute | Defense-in-depth |

---

## Commit 1 — Vuln 2: Token Body Exposure

### Problema

`/auth/login` y `/auth/refresh` retornan `access_token` y `refresh_token` en el body JSON vía `TokenResponse`. Cualquier JS ejecutándose en el contexto de la página puede leer el refresh token del response body, anulando la defensa HttpOnly de las cookies.

El frontend nunca lee estos campos (verificado: `lib/stores/auth.ts` solo guarda `UserResponse`; `lib/api/client.ts` llama `/auth/refresh` directamente vía `fetch` sin leer el body).

### Decisión

Reemplazar `TokenResponse` con `AuthSuccessResponse(expires_in: int)`. Las cookies transportan los tokens; el body queda limpio de credentials.

### Archivos afectados

**`backend/app/schemas/models.py`**
- Eliminar `TokenResponse` (campos `access_token`, `refresh_token`, `token_type`)
- Agregar:
  ```python
  class AuthSuccessResponse(BaseModel):
      expires_in: int  # segundos hasta que expira el access token
  ```

**`backend/app/routers/auth.py`**
- Import: `TokenResponse` → `AuthSuccessResponse`
- `/auth/login`: `response_model=AuthSuccessResponse`, retornar `AuthSuccessResponse(expires_in=settings.jwt_access_token_expire_minutes * 60)`
- `/auth/refresh`: ídem

**`backend/tests/test_auth.py`**

`test_login_success` — invertir assertions de body:
```python
# Antes
assert "access_token" in body
assert "refresh_token" in body
assert body["token_type"] == "bearer"
# Después
assert "access_token" not in body
assert "refresh_token" not in body
assert "expires_in" in body
```

`test_refresh_issues_new_token_pair` — mismo tratamiento (líneas 171-172).

**`frontend/lib/api/types.ts`**
- Reducir `TokenResponse` a solo `expires_in`:
  ```ts
  export interface TokenResponse {
    expires_in: number;
  }
  ```
  (mantener nombre `TokenResponse` para minimizar diff en `auth.ts`)

**`frontend/lib/api/auth.ts`**
- `login()` y `refresh()`: tipos de retorno ya apuntan a `TokenResponse`. Sin cambios de nombre necesarios; el tipo actualizado en `types.ts` propaga automáticamente.

### Gotchas resueltos

- `services/auth.py:39,57,66` usa `token_type` como claim interno del JWT (`"access"`/`"refresh"`), completamente independiente del `token_type: "bearer"` del response body. Sin cambios.
- `client.ts` llama `fetch('/auth/refresh')` directamente sin leer body. Sin cambios.
- `login/page.tsx`: `onSuccess: () => router.push("/")` — no usa el return value.
- `register/page.tsx`: `await login(body)` sin destructurar resultado.
- `.next/` es build cache generado; se regenera con `pnpm build`.

---

## Commit 2 — Vuln 1: Strip PHI de result_json + regenerar en lectura

### Problema

`_persist_scan_history` serializa `ScanResponse` completo incluyendo `personalized_insights`, que contiene valores de biomarcadores PHI (colesterol, HDL, HbA1c, etc.) junto con narrativa generada por Gemini que menciona los valores verbatim. La columna `result_json` es JSON plaintext — sin cifrado, sin IV, sin TTL.

Esto contradice dos reglas de `.claude/CLAUDE.md`:
- "Los datos médicos se encriptan con AES-256 antes de persistir"
- "Los datos de biomarkers expiran en 180 días"

Además, `DELETE /biosync/data` no toca `scan_history`, dejando PHI accesible tras el borrado solicitado por el usuario (violación GDPR right-to-erasure).

### Decisión (Opción A1)

Strip de `personalized_insights` en escritura. Regenerar en lectura usando los biomarcadores cifrados actuales del usuario. Migración retroactiva para filas existentes.

### Extracción de función standalone

El nodo `make_personalize_node` no tiene dependencias de grafo — solo necesita `resolved: list[IngredientResult]`, `biomarkers: list | None`, y `settings`. Extraer la lógica interna a:

**`backend/app/services/analysis.py`**
```python
async def generate_personalized_insights(
    resolved: list[IngredientResult],
    biomarkers: list | None,
    settings: Settings,
) -> list[PersonalizedInsight]:
    """Standalone version of make_personalize_node's inner logic.

    Called from GET /scan/result/{barcode} and POST /scan/photo/{pseudo_barcode}/link
    to regenerate PHI-containing insights on read instead of persisting them.
    """
```
Mueve la lógica de `_build_insight` + `find_ingredient_matches` + `gather` aquí.

**`backend/app/agents/nodes.py`**
- `make_personalize_node` delega a `generate_personalized_insights`. Sin breaking changes al grafo.

### Archivos afectados

**`backend/app/routers/scan.py` — `_persist_scan_history`**
```python
# Antes
result_json=response.model_dump(mode="json", exclude={"show_barcode_cta"})
# Después
result_json=response.model_dump(mode="json", exclude={"show_barcode_cta", "personalized_insights"})
```

**`backend/app/routers/scan.py` — `get_scan_result`**
- Cambiar `def` → `async def` (necesario para `await generate_personalized_insights(...)`)
- Post-hidratación: cargar `Biomarker` del usuario → `decrypt_biomarker` → llamar `generate_personalized_insights` → adjuntar a `response.personalized_insights`
- Si el usuario no tiene biomarcadores activos: `personalized_insights=[]` (comportamiento correcto — `ScanResponse.personalized_insights` tiene `default=[]` en el schema, por lo que `model_validate` sobre JSON sin esa clave ya produce lista vacía)

**`backend/app/routers/scan.py` — `link_photo_barcode`**
- Ya es `async def`. Mismo tratamiento post-hidratación que `get_scan_result`.

**`backend/app/services/maintenance.py`**
```python
def scrub_scan_history_insights(db: Session, user_id: str) -> int:
    """Remove personalized_insights from result_json for all scans of a user.

    Does NOT commit — caller is responsible for committing.
    Returns number of rows updated.
    """
```
Itera sobre `ScanHistory` rows del user, filtra la clave del dict, asigna de vuelta.

**`backend/app/routers/biosync.py` — `delete_biomarkers`**

Nuevo flujo (scrub siempre, antes del 404 check):
```python
def delete_biomarkers(...):
    scrub_scan_history_insights(db, str(current_user.id))
    biomarker = db.scalar(select(Biomarker).where(Biomarker.user_id == current_user.id))
    if not biomarker:
        db.commit()  # persiste el scrub aunque no haya Biomarker row
        raise HTTPException(status_code=404, detail="No biomarker data for this user")
    db.delete(biomarker)
    db.commit()  # persiste scrub + delete en una sola transacción
```

### Gotchas resueltos

- `GET /scan/history` retorna `ScanHistoryEntry` (solo columnas ORM: semaphore, scanned_at, etc.) — **no toca `result_json`**. Sin cambios necesarios.
- `get_scan_result` es `def` síncrono → debe convertirse a `async def` para poder `await` la regeneración.
- `link_photo_barcode` (línea 275) también lee `result_json` y retorna `ScanResponse` — cubierto por el diseño.
- Escenario GDPR edge case: usuario con PHI en scan_history cuyo Biomarker row fue purgado por el cron de TTL → DELETE /biosync/data recibía 404 sin scrubear. Resuelto: scrub ocurre ANTES del 404 check y se commitea en ambas ramas.
- `scrub_scan_history_insights` NO commitea internamente — el handler controla la transacción y puede commitear scrub + delete en un solo commit.

---

## Commit 3 — Vuln 1: Data Migration

### Problema

Filas existentes en `scan_history.result_json` contienen `personalized_insights` con PHI en plaintext. El Commit 2 solo protege escrituras futuras.

### Decisión

Nueva versión Alembic (data migration). Sin cambio de schema — `result_json` permanece como columna `JSON`. Solo actualiza datos.

**`backend/alembic/versions/<new_rev>_scrub_phi_from_scan_history.py`**
- `down_revision = "518f2aab47ed"` (head actual)
- `upgrade()`: carga todas las filas con `result_json` no-null, elimina la clave `personalized_insights` si existe, guarda de vuelta. Iteración Python-level para compatibilidad SQLite + PostgreSQL.
- `downgrade()`: no-op (PHI no se puede restaurar; es intencional).

---

## Commit 4 — D1: Secrets Validator en Settings

### Problema

`config.py` define `jwt_secret = "dev-secret-change-in-production"` y `aes_key = "dev-aes-key-32-bytes-changethis!"` como defaults. Sin validación de startup, un deploy que olvide setear las env vars arranca con secrets predecibles.

### Decisión

`model_validator(mode="after")` en `Settings`:

**`backend/app/config.py`**
```python
from pydantic import model_validator

_DEV_SECRETS = {
    "dev-secret-change-in-production",
    "dev-aes-key-32-bytes-changethis!",
}

@model_validator(mode="after")
def reject_dev_secrets_in_production(self) -> "Settings":
    if not self.debug:
        if self.jwt_secret in _DEV_SECRETS or self.aes_key in _DEV_SECRETS:
            raise ValueError(
                "jwt_secret and aes_key must be overridden in production (debug=False)"
            )
    return self
```

### Gotchas resueltos

- `conftest.py` usa `debug=True` en `TEST_SETTINGS` → validator nunca dispara en tests. Seguro.
- `get_settings()` tiene `@lru_cache`. Si la validación falla en startup, el error se propaga en la primera llamada a `get_settings()` y el servidor no levanta. Comportamiento correcto.

---

## Commit 5 — D2: Logout revoca todos los tokens (L1)

### Problema

El refresh cookie tiene `path="/auth/refresh"`, así que el browser no lo envía a `/auth/logout`. `revoke_user_token(db, refresh_token)` nunca se ejecuta — los tokens del usuario permanecen activos en DB tras logout.

### Decisión (L1)

Requerir JWT de acceso en logout y revocar todos los tokens del usuario via `revoke_all_user_tokens` (ya existe en `services/auth.py:183`).

**`backend/app/routers/auth.py` — `logout`**
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

Eliminar: parámetro `refresh_token: str | None = Cookie(...)` y la llamada a `revoke_user_token`.
Agregar import: `revoke_all_user_tokens` desde `app.services.auth`.

### Gotchas resueltos

- `revoke_all_user_tokens` ya existe — no hay que crearla.
- `test_logout_clears_cookies`: el test hace login antes de logout, por lo que el client jar tiene el cookie `access_token`. `get_current_user` lo lee sin problema. Test pasa sin modificaciones.
- `get_current_user` depende de `db` y `settings` — FastAPI los inyecta normalmente. Sin cambios en el dependency graph del endpoint.

---

## Commit 6 — D3: Security Headers Middleware

### Problema

Las responses no incluyen headers de seguridad HTTP estándar (HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy).

### Decisión

Middleware HTTP inline en `main.py` via decorador `@app.middleware("http")` — siempre el más externo, sin ambigüedad de orden con `CORSMiddleware` ni `SlowAPIMiddleware`.

**`backend/app/main.py`**
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

### Gotchas resueltos

- `add_middleware` es LIFO — orden ambiguo con CORS. El decorador `@app.middleware("http")` evita este problema: siempre es el wrapper más externo.
- HSTS solo en `not settings.debug` — sin HTTPS en dev local, HSTS bloquearía el navegador.
- `X-XSS-Protection: 0` es la recomendación moderna (browsers modernos ignoran el header antiguo; `1` puede introducir vulnerabilidades en browsers viejos).

---

## Commit 7 — D4: Ownership Check en /scan/contribute

### Problema

`POST /scan/contribute` acepta `scan_history_id` (UUID opcional) sin verificar que pertenezca al usuario autenticado. No es explotable hoy (el campo es solo auditoría, no expone datos del scan referenciado), pero es un hardening preventivo contra regresiones futuras.

### Decisión

**`backend/app/routers/scan.py` — `scan_contribute`**

Agregar antes de crear el `OFFContribution` row:
```python
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
```

### Gotchas resueltos

- `body.scan_history_id` es `UUID | None` — el guard `if body.scan_history_id is not None:` es necesario para no lanzar 403 cuando el campo no viene en el request.
- El check usa `ScanHistory.user_id == current_user.id` — filtra por ownership real, no solo existencia del UUID.

---

## Archivos modificados — resumen completo

| Archivo | Commit(s) |
|---------|-----------|
| `backend/app/schemas/models.py` | 1 |
| `backend/app/routers/auth.py` | 1, 5 |
| `backend/tests/test_auth.py` | 1 |
| `frontend/lib/api/types.ts` | 1 |
| `frontend/lib/api/auth.ts` | 1 |
| `backend/app/services/analysis.py` | 2 |
| `backend/app/agents/nodes.py` | 2 |
| `backend/app/routers/scan.py` | 2, 7 |
| `backend/app/services/maintenance.py` | 2 |
| `backend/app/routers/biosync.py` | 2 |
| `backend/alembic/versions/<new_rev>_scrub_phi_from_scan_history.py` | 3 |
| `backend/app/config.py` | 4 |
| `backend/app/main.py` | 6 |

---

## No requieren cambios (verificado)

- `frontend/lib/api/client.ts` — interceptor de refresh llama `fetch` directo, no lee body
- `frontend/lib/stores/auth.ts` — solo almacena `UserResponse`, nunca tokens
- `frontend/app/(auth)/login/page.tsx` — `onSuccess` no usa return value de `login()`
- `frontend/app/(auth)/register/page.tsx` — `await login(body)` sin destructurar
- `backend/app/services/auth.py` — `token_type` es claim JWT interno, no campo de response
- `backend/app/routers/scan.py:get_scan_history` — retorna `ScanHistoryEntry` desde columnas ORM, no toca `result_json`
- `backend/tests/test_auth.py:test_logout_clears_cookies` — cliente tiene access_token cookie post-login; L1 logout funciona sin cambios en el test
