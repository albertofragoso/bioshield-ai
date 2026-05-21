# Scan Result Sharing

**Fecha:** 2026-05-21  
**Estado:** Aprobado — listo para implementación  
**Spec relacionado:** —

---

## Contexto

Los usuarios quieren compartir el resultado de un scan con su médico o nutriólogo. La ruta actual `/scan/[id]` requiere autenticación (JWT HttpOnly cookie), por lo que no es compartible directamente.

El diseño usa un **secret link** con token de 144-bit de entropía — igual al modelo de Figma/Google Docs. El destinatario no necesita cuenta. El usuario puede revocar el link cuando quiera.

---

## Arquitectura

### Schema — `ScanHistory`

Dos columnas nuevas en `scan_history`:

```python
share_token: Mapped[str | None] = mapped_column(
    String(32), nullable=True, unique=True, index=True
)
share_expires_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

- `share_token`: generado con `secrets.token_urlsafe(24)` → 32 chars, 144 bits de entropía. `NULL` cuando no se ha generado o fue revocado.
- `share_expires_at`: `now() + SHARE_LINK_TTL_DAYS` (default 7, configurable via env). El endpoint GET verifica que no haya expirado.

Alembic migration nueva.

### Endpoints (backend)

**`POST /scan/{scan_id}/share`** (auth requerida)

```python
scan = db.query(ScanHistory).filter_by(
    id=scan_id, user_id=current_user.id   # ownership check — nunca omitir
).first()
if not scan:
    raise HTTPException(403)
if not scan.share_token:
    scan.share_token = secrets.token_urlsafe(24)
    scan.share_expires_at = datetime.now(UTC) + timedelta(days=settings.share_link_ttl_days)
    db.commit()
return {"share_url": f"{settings.frontend_url}/scan/share/{scan.share_token}", "expires_at": scan.share_expires_at}
```

Si ya tiene token, retorna el existente (idempotente).

**`DELETE /scan/{scan_id}/share`** (auth requerida)

```python
scan = db.query(ScanHistory).filter_by(
    id=scan_id, user_id=current_user.id   # mismo ownership check
).first()
if not scan:
    raise HTTPException(403)
scan.share_token = None
scan.share_expires_at = None
db.commit()
return Response(status_code=204)
```

**`GET /scan/share/{token}`** (público, sin auth)

```python
scan = db.query(ScanHistory).filter_by(share_token=token).first()
if not scan:
    raise HTTPException(404)
if scan.share_expires_at and scan.share_expires_at < datetime.now(UTC):
    raise HTTPException(410, "Link expirado")
result = ScanResponse.model_validate(scan.result_json)
return ScanShareProjection.model_validate(result.model_dump())
```

**`ScanShareProjection` — Pydantic model de proyección (nunca exponer `result_json` raw):**

```python
class ScanShareProjection(BaseModel):
    product_name: str | None = None
    product_barcode: str
    semaphore: SemaphoreColor
    ingredients: list[IngredientResult]
    conflict_severity: ConflictSeverity | None = None
    scanned_at: datetime
    personalized_insights: list[PersonalizedInsight] = []
    # excluidos: user_id, id, result_json, share_token, status, internal metadata
```

Rate limiting: el middleware `slowapi` existente aplica al endpoint público con un límite conservador (ej. 60/min por IP).

### Settings (`backend/app/config.py`)

```python
share_link_ttl_days: int = Field(default=7, description="Days until share link expires")
frontend_url: str = Field(default="http://localhost:3000")
```

### GDPR / account deletion

`ScanHistory.user_id` ya tiene FK a `users.id`. Agregar `ON DELETE CASCADE` en la migration para que al borrar un user, sus scan rows (y share tokens) se eliminen automáticamente.

---

## Frontend

### Scan result page (`/scan/[id]/page.tsx`)

Nuevo botón "Compartir" en el header del resultado:

```tsx
<ShareButton scanId={scan.product_barcode} />
```

**`ShareButton` component (`frontend/components/scanner/ShareButton.tsx`):**

```tsx
// Al hacer click:
// 1. Si ya tiene shareUrl en cache → copiar al clipboard
// 2. Si no → POST /scan/{scanId}/share → guardar en TanStack Query cache → copiar
// 3. Toast: "Link copiado"
// 4. Botón adicional "Revocar link" si shareUrl existe
```

El `shareUrl` y `expiresAt` se guardan en TanStack Query con key `["share", scanId]`. Al refrescar, el frontend hace GET del scan result que no incluye el share_token (security), así que necesita re-fetch de `["share", scanId]` si quiere mostrar el botón "Revocar". Esto es aceptable — el botón de revocar solo aparece en la misma sesión o si el share fue creado previamente.

### Nueva ruta pública `/scan/share/[token]`

- Sin auth guard (no incluir en el `(app)` route group)
- Hace `GET /scan/share/{token}` (endpoint público)
- Renderiza la misma UI que `/scan/[id]` pero:
  - Sin botón "Compartir"
  - Sin botón "Revocar"
  - Badge sutil en el header: `"Resultado compartido · expira {fecha}"`
  - Sin acceso al historial del usuario

**Archivos a crear/modificar:**

| Archivo | Cambio |
|---------|--------|
| `backend/app/schemas/models.py` | nuevo `ScanShareProjection` model |
| `backend/app/routers/scan.py` | 3 nuevos endpoints |
| `backend/app/config.py` | `share_link_ttl_days`, `frontend_url` |
| `backend/app/models/__init__.py` | columnas `share_token`, `share_expires_at` en `ScanHistory` |
| `alembic/versions/` | nueva migration |
| `frontend/components/scanner/ShareButton.tsx` | nuevo componente |
| `frontend/app/(app)/scan/[id]/page.tsx` | agregar `<ShareButton>` |
| `frontend/app/scan/share/[token]/page.tsx` | nueva ruta pública (fuera del route group `(app)`) |
| `frontend/lib/api/scan.ts` | funciones `createShareLink()`, `revokeShareLink()`, `getSharedScan()` |

---

## Tests

### Backend (pytest)
- `test_create_share_link` — POST crea token, retorna URL con `expires_at`
- `test_create_share_link_idempotent` — segundo POST retorna el mismo token
- `test_share_link_ownership` — usuario B no puede crear/revocar share del usuario A (verifica 403)
- `test_get_shared_scan_public` — GET sin auth retorna `ScanShareProjection` correctamente
- `test_get_shared_scan_no_user_id` — verifica que `user_id` NO está en la respuesta pública
- `test_get_shared_scan_expired` — link expirado retorna 410
- `test_revoke_share_link` — DELETE pone `share_token = NULL`; GET subsecuente retorna 404

### E2E (Playwright)
- `share_link_copies_to_clipboard` — click "Compartir" → clipboard contiene URL
- `shared_scan_page_loads_without_auth` — navegar a `/scan/share/{token}` sin sesión → resultado visible
- `shared_scan_no_share_button` — la página compartida no muestra el botón de compartir

---

## Verificación

1. `curl -X POST /scan/{id}/share -H "Cookie: ..."` como usuario A → retorna `share_url`
2. `curl -X POST /scan/{id}/share -H "Cookie: ..."` como usuario B → retorna 403
3. `curl /scan/share/{token}` (sin Cookie) → retorna resultado completo sin `user_id`
4. Modificar `share_expires_at` en DB a pasado → `curl` retorna 410
5. `DELETE /scan/{id}/share` como usuario A → GET del share retorna 404
