# Scan Result Sharing — Implementation Plan

> **IMPLEMENTADO ✅ — PR #24** (feature/scan-sharing → main, 2026-05-22)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Agregar URLs secretas compartibles a los resultados de scan para que el usuario pueda compartirlos con su médico sin requerir que el destinatario tenga cuenta.

**Architecture:** Columnas `share_token` y `share_expires_at` en `ScanHistory`. Tres endpoints: POST (genera token), DELETE (revoca), GET público (sin auth). Frontend: botón "Compartir" en scan result, nueva ruta pública `/scan/share/[token]`. `ScanShareProjection` allowlist model garantiza que no se filtren campos sensibles.

**Tech Stack:** FastAPI 0.115, SQLAlchemy 2.0, Alembic, Pydantic v2, Next.js 16.2 App Router, TanStack Query v5, TypeScript

---

## Archivos a crear/modificar

| Archivo | Cambio |
|---------|--------|
| `backend/app/models/__init__.py` | Columnas `share_token`, `share_expires_at` en `ScanHistory` |
| `alembic/versions/<rev>_add_share_token.py` | Migration: columnas share |
| `backend/app/config.py` | Settings: `share_link_ttl_days`, `frontend_url` |
| `backend/app/schemas/models.py` | Nuevo model `ScanShareProjection` |
| `backend/app/routers/scan.py` | 3 nuevos endpoints: POST/DELETE/GET share |
| `backend/tests/test_scan.py` | 7 nuevos tests de sharing |
| `frontend/lib/api/scan.ts` | `createShareLink()`, `revokeShareLink()`, `getSharedScan()` |
| `frontend/components/scanner/ShareButton.tsx` | Nuevo componente |
| `frontend/app/(app)/scan/[id]/page.tsx` | Integrar `<ShareButton>` |
| `frontend/app/scan/share/[token]/page.tsx` | Nueva ruta pública (fuera del route group `(app)`) |

---

### Task 1: Columnas share en ScanHistory + Migration

**Files:**
- Modify: `backend/app/models/__init__.py`
- Create: `alembic/versions/<rev>_add_share_token.py`

- [x] **Step 1: Escribir el test failing**

```python
# backend/tests/test_scan.py
async def test_scan_history_has_share_columns(db_session: AsyncSession):
    """ScanHistory tiene share_token y share_expires_at."""
    from backend.app.models import ScanHistory
    import inspect
    cols = {c.key for c in inspect(ScanHistory).mapper.columns}
    assert "share_token" in cols
    assert "share_expires_at" in cols
```

- [x] **Step 2: Correr el test para verificar que falla**

```bash
cd backend && python -m pytest tests/test_scan.py::test_scan_history_has_share_columns -v
```

Esperado: `FAILED`

- [x] **Step 3: Agregar columnas al modelo**

En `backend/app/models/__init__.py`, dentro de la clase `ScanHistory`:

```python
from datetime import datetime

share_token: Mapped[str | None] = mapped_column(
    String(32), nullable=True, unique=True, index=True
)
share_expires_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

Verificar que `String`, `DateTime` ya están importados del modulo de SQLAlchemy. Si no:
```python
from sqlalchemy import String, DateTime
```

- [x] **Step 4: Generar migration**

```bash
cd backend && alembic revision --autogenerate -m "add_share_token"
```

El archivo generado debe tener:
```python
def upgrade() -> None:
    op.add_column('scan_history',
        sa.Column('share_token', sa.String(32), nullable=True))
    op.add_column('scan_history',
        sa.Column('share_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint('uq_scan_history_share_token', 'scan_history', ['share_token'])
    op.create_index('ix_scan_history_share_token', 'scan_history', ['share_token'])

def downgrade() -> None:
    op.drop_index('ix_scan_history_share_token', table_name='scan_history')
    op.drop_constraint('uq_scan_history_share_token', 'scan_history', type_='unique')
    op.drop_column('scan_history', 'share_expires_at')
    op.drop_column('scan_history', 'share_token')
```

Si Alembic no genera los constraints automáticamente, agregarlos manualmente.

- [x] **Step 5: Aplicar migration**

```bash
cd backend && alembic upgrade head
```

- [x] **Step 6: Correr el test**

```bash
cd backend && python -m pytest tests/test_scan.py::test_scan_history_has_share_columns -v
```

Esperado: `PASSED`

- [x] **Step 7: Commit**

```bash
git add backend/app/models/__init__.py alembic/versions/*_add_share_token.py
git commit -m "feat(db): add share_token and share_expires_at to scan_history"
```

---

### Task 2: Settings `share_link_ttl_days` y `frontend_url`

**Files:**
- Modify: `backend/app/config.py`

- [x] **Step 1: Agregar los campos en la clase `Settings`**

Localizar la clase `Settings` en `backend/app/config.py` y agregar:

```python
share_link_ttl_days: int = Field(default=7, description="Days until share link expires")
frontend_url: str = Field(default="http://localhost:3000")
```

- [x] **Step 2: Verificar que la app arranca sin errores**

```bash
cd backend && python -c "from app.config import settings; print(settings.share_link_ttl_days, settings.frontend_url)"
```

Esperado: `7 http://localhost:3000`

- [x] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat(config): add share_link_ttl_days and frontend_url settings"
```

---

### Task 3: `ScanShareProjection` Pydantic model

**Files:**
- Modify: `backend/app/schemas/models.py`

- [x] **Step 1: Escribir test failing**

```python
# backend/tests/test_scan.py
def test_scan_share_projection_excludes_sensitive_fields():
    """ScanShareProjection no expone user_id, id, share_token, result_json."""
    from backend.app.schemas.models import ScanShareProjection
    fields = ScanShareProjection.model_fields
    assert "user_id" not in fields
    assert "id" not in fields
    assert "share_token" not in fields
    assert "result_json" not in fields

def test_scan_share_projection_has_required_fields():
    """ScanShareProjection contiene los campos públicos."""
    from backend.app.schemas.models import ScanShareProjection
    fields = ScanShareProjection.model_fields
    assert "product_barcode" in fields
    assert "semaphore" in fields
    assert "ingredients" in fields
    assert "scanned_at" in fields
```

- [x] **Step 2: Correr tests para verificar que fallan**

```bash
cd backend && python -m pytest tests/test_scan.py::test_scan_share_projection_excludes_sensitive_fields tests/test_scan.py::test_scan_share_projection_has_required_fields -v
```

Esperado: `FAILED — ImportError o AttributeError`

- [x] **Step 3: Agregar el model en `schemas/models.py`**

Añadir al final del archivo (antes del último `if __name__`):

```python
class ScanShareProjection(BaseModel):
    """Proyección pública de un scan result. Solo campos seguros para compartir."""
    product_name: str | None = None
    product_barcode: str
    semaphore: SemaphoreColor
    ingredients: list[IngredientResult]
    conflict_severity: ConflictSeverity | None = None
    scanned_at: datetime
    personalized_insights: list[PersonalizedInsight] = []
```

Verificar que `SemaphoreColor`, `ConflictSeverity`, `IngredientResult`, `PersonalizedInsight`, `datetime` ya están importados en el archivo. Si falta `datetime`:
```python
from datetime import datetime
```

- [x] **Step 4: Correr tests**

```bash
cd backend && python -m pytest tests/test_scan.py::test_scan_share_projection_excludes_sensitive_fields tests/test_scan.py::test_scan_share_projection_has_required_fields -v
```

Esperado: `PASSED`

- [x] **Step 5: Commit**

```bash
git add backend/app/schemas/models.py
git commit -m "feat(schemas): add ScanShareProjection allowlist model"
```

---

### Task 4: Endpoints POST, DELETE, GET share

**Files:**
- Modify: `backend/app/routers/scan.py`

- [x] **Step 1: Escribir los 7 tests failing**

```python
# backend/tests/test_scan.py

# Helper: crear un ScanHistory con result_json seeded
async def _seed_scan(db_session: AsyncSession, user_id: int, barcode: str = "1234567890"):
    from backend.app.models import ScanHistory
    import json
    row = ScanHistory(
        product_barcode=barcode,
        user_id=user_id,
        result_json={
            "product_barcode": barcode,
            "product_name": "Test",
            "semaphore": "GREEN",
            "ingredients": [],
            "conflict_severity": None,
            "scanned_at": "2026-05-21T10:00:00Z",
            "personalized_insights": [],
            "show_barcode_cta": False,
            "source": "barcode",
        },
        status="done",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


async def test_create_share_link(client: AsyncClient, db_session: AsyncSession):
    """POST /scan/{id}/share retorna share_url y expires_at."""
    row = await _seed_scan(db_session, user_id=1)
    response = await client.post(
        f"/scan/{row.id}/share",
        cookies={"access_token": make_test_jwt(user_id=1)},
    )
    assert response.status_code == 200
    body = response.json()
    assert "share_url" in body
    assert "expires_at" in body
    assert "/scan/share/" in body["share_url"]


async def test_create_share_link_idempotent(client: AsyncClient, db_session: AsyncSession):
    """Segundo POST retorna el mismo token."""
    row = await _seed_scan(db_session, user_id=1)
    r1 = await client.post(f"/scan/{row.id}/share", cookies={"access_token": make_test_jwt(user_id=1)})
    r2 = await client.post(f"/scan/{row.id}/share", cookies={"access_token": make_test_jwt(user_id=1)})
    assert r1.json()["share_url"] == r2.json()["share_url"]


async def test_share_link_ownership_forbidden(client: AsyncClient, db_session: AsyncSession):
    """Usuario B no puede crear share del scan de usuario A."""
    row = await _seed_scan(db_session, user_id=1)
    response = await client.post(
        f"/scan/{row.id}/share",
        cookies={"access_token": make_test_jwt(user_id=2)},
    )
    assert response.status_code == 403


async def test_get_shared_scan_public(client: AsyncClient, db_session: AsyncSession):
    """GET /scan/share/{token} sin auth retorna ScanShareProjection."""
    from datetime import UTC, timedelta
    import secrets
    row = await _seed_scan(db_session, user_id=1)
    row.share_token = secrets.token_urlsafe(24)
    row.share_expires_at = datetime.now(UTC) + timedelta(days=7)
    await db_session.commit()

    response = await client.get(f"/scan/share/{row.share_token}")
    assert response.status_code == 200
    body = response.json()
    assert "product_barcode" in body
    assert "semaphore" in body


async def test_get_shared_scan_no_user_id(client: AsyncClient, db_session: AsyncSession):
    """La respuesta pública NO contiene user_id."""
    from datetime import UTC, timedelta
    import secrets
    row = await _seed_scan(db_session, user_id=1)
    row.share_token = secrets.token_urlsafe(24)
    row.share_expires_at = datetime.now(UTC) + timedelta(days=7)
    await db_session.commit()

    response = await client.get(f"/scan/share/{row.share_token}")
    body = response.json()
    assert "user_id" not in body
    assert "id" not in body
    assert "share_token" not in body


async def test_get_shared_scan_expired(client: AsyncClient, db_session: AsyncSession):
    """Link expirado retorna 410 Gone."""
    from datetime import UTC, timedelta
    import secrets
    row = await _seed_scan(db_session, user_id=1)
    row.share_token = secrets.token_urlsafe(24)
    row.share_expires_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.commit()

    response = await client.get(f"/scan/share/{row.share_token}")
    assert response.status_code == 410


async def test_revoke_share_link(client: AsyncClient, db_session: AsyncSession):
    """DELETE /scan/{id}/share pone share_token=NULL; GET subsecuente retorna 404."""
    from datetime import UTC, timedelta
    import secrets
    row = await _seed_scan(db_session, user_id=1)
    row.share_token = secrets.token_urlsafe(24)
    row.share_expires_at = datetime.now(UTC) + timedelta(days=7)
    await db_session.commit()

    token = row.share_token

    del_response = await client.delete(
        f"/scan/{row.id}/share",
        cookies={"access_token": make_test_jwt(user_id=1)},
    )
    assert del_response.status_code == 204

    get_response = await client.get(f"/scan/share/{token}")
    assert get_response.status_code == 404
```

- [x] **Step 2: Correr tests para verificar que fallan**

```bash
cd backend && python -m pytest tests/test_scan.py -k "share" -v
```

Esperado: todos `FAILED — 404 Not Found` (endpoints no existen).

- [x] **Step 3: Implementar los 3 endpoints**

En `backend/app/routers/scan.py`, agregar al final del router (antes del cierre del archivo):

```python
import secrets
from datetime import UTC, timedelta

# --- Scan Sharing Endpoints ---

class ShareResponse(BaseModel):
    share_url: str
    expires_at: datetime


@router.post("/{scan_id}/share", response_model=ShareResponse)
async def create_share_link(
    scan_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    # Ownership check — nunca omitir.
    scan = await db.scalar(
        select(ScanHistory).where(
            ScanHistory.id == scan_id,
            ScanHistory.user_id == current_user.id,
        )
    )
    if not scan:
        raise HTTPException(status_code=403)

    if not scan.share_token:
        scan.share_token = secrets.token_urlsafe(24)
        scan.share_expires_at = datetime.now(UTC) + timedelta(
            days=settings.share_link_ttl_days
        )
        await db.commit()
        await db.refresh(scan)

    return ShareResponse(
        share_url=f"{settings.frontend_url}/scan/share/{scan.share_token}",
        expires_at=scan.share_expires_at,
    )


@router.delete("/{scan_id}/share", status_code=204)
async def revoke_share_link(
    scan_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    scan = await db.scalar(
        select(ScanHistory).where(
            ScanHistory.id == scan_id,
            ScanHistory.user_id == current_user.id,
        )
    )
    if not scan:
        raise HTTPException(status_code=403)

    scan.share_token = None
    scan.share_expires_at = None
    await db.commit()


@router.get("/share/{token}", response_model=ScanShareProjection)
async def get_shared_scan(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    scan = await db.scalar(
        select(ScanHistory).where(ScanHistory.share_token == token)
    )
    if not scan:
        raise HTTPException(status_code=404)

    if scan.share_expires_at and scan.share_expires_at < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Link expirado")

    result = ScanResponse.model_validate(scan.result_json)
    return ScanShareProjection.model_validate(result.model_dump())
```

Agregar imports si faltan:
```python
from backend.app.schemas.models import ScanShareProjection
```

**Nota de orden de rutas:** `/share/{token}` debe registrarse ANTES de `/{scan_id}/share` si comparten el mismo prefijo, o mejor aún — verificar que el router de FastAPI no tenga ambigüedad entre `/share/{token}` (GET, público) y `/{scan_id}/share` (POST/DELETE, autenticado). Son métodos distintos en el mismo router, FastAPI no confundirá `share` con un `scan_id` entero.

- [x] **Step 4: Correr los 7 tests**

```bash
cd backend && python -m pytest tests/test_scan.py -k "share" -v
```

Esperado: todos `PASSED`.

- [x] **Step 5: Commit**

```bash
git add backend/app/routers/scan.py backend/tests/test_scan.py
git commit -m "feat(scan): add share link endpoints POST/DELETE/GET"
```

---

### Task 5: API functions en `frontend/lib/api/scan.ts`

**Files:**
- Modify: `frontend/lib/api/scan.ts`

- [x] **Step 1: Agregar las tres funciones al final del archivo**

```typescript
// frontend/lib/api/scan.ts

export interface ShareLinkResponse {
  share_url: string;
  expires_at: string;
}

export interface ScanShareProjection {
  product_name: string | null;
  product_barcode: string;
  semaphore: string;
  ingredients: IngredientResult[];
  conflict_severity: string | null;
  scanned_at: string;
  personalized_insights: PersonalizedInsight[];
}

export async function createShareLink(scanId: number): Promise<ShareLinkResponse> {
  const res = await fetch(`/api/scan/${scanId}/share`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Share link creation failed: ${res.status}`);
  return res.json();
}

export async function revokeShareLink(scanId: number): Promise<void> {
  const res = await fetch(`/api/scan/${scanId}/share`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok && res.status !== 204) throw new Error(`Revoke failed: ${res.status}`);
}

export async function getSharedScan(token: string): Promise<ScanShareProjection> {
  const res = await fetch(`/api/scan/share/${token}`);
  if (res.status === 410) throw new Error("EXPIRED");
  if (!res.ok) throw new Error(`Shared scan fetch failed: ${res.status}`);
  return res.json();
}
```

- [x] **Step 2: Verificar TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "api/scan"
```

Esperado: sin errores.

- [x] **Step 3: Commit**

```bash
git add frontend/lib/api/scan.ts
git commit -m "feat(frontend): add createShareLink, revokeShareLink, getSharedScan API functions"
```

---

### Task 6: Componente `ShareButton`

**Files:**
- Create: `frontend/components/scanner/ShareButton.tsx`

- [x] **Step 1: Crear el componente**

```tsx
// frontend/components/scanner/ShareButton.tsx
"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { createShareLink, revokeShareLink } from "@/lib/api/scan";

interface ShareButtonProps {
  scanDbId: number;
}

export function ShareButton({ scanDbId }: ShareButtonProps) {
  const queryClient = useQueryClient();
  const cacheKey = ["share", scanDbId];

  // shareUrl viene del cache de TanStack Query para esta sesión.
  const cachedShare = queryClient.getQueryData<{ share_url: string; expires_at: string }>(cacheKey);

  const [shareUrl, setShareUrl] = useState<string | null>(cachedShare?.share_url ?? null);

  const shareMutation = useMutation({
    mutationFn: () => createShareLink(scanDbId),
    onSuccess: (data) => {
      queryClient.setQueryData(cacheKey, data);
      setShareUrl(data.share_url);
      navigator.clipboard.writeText(data.share_url).catch(() => null);
      toast.success("Link copiado al portapapeles");
    },
    onError: () => {
      toast.error("No se pudo generar el link");
    },
  });

  const revokeMutation = useMutation({
    mutationFn: () => revokeShareLink(scanDbId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: cacheKey });
      setShareUrl(null);
      toast.success("Link revocado");
    },
    onError: () => {
      toast.error("No se pudo revocar el link");
    },
  });

  const handleShare = () => {
    if (shareUrl) {
      navigator.clipboard.writeText(shareUrl).catch(() => null);
      toast.success("Link copiado al portapapeles");
      return;
    }
    shareMutation.mutate();
  };

  return (
    <div className="flex gap-2">
      <button
        onClick={handleShare}
        disabled={shareMutation.isPending}
        className="text-sm font-medium text-subtext hover:text-text transition-colors"
      >
        {shareMutation.isPending ? "Generando..." : "Compartir"}
      </button>

      {shareUrl && (
        <button
          onClick={() => revokeMutation.mutate()}
          disabled={revokeMutation.isPending}
          className="text-sm font-medium text-red-400 hover:text-red-600 transition-colors"
        >
          {revokeMutation.isPending ? "Revocando..." : "Revocar link"}
        </button>
      )}
    </div>
  );
}
```

- [x] **Step 2: Verificar TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "ShareButton"
```

Esperado: sin errores.

- [x] **Step 3: Commit**

```bash
git add frontend/components/scanner/ShareButton.tsx
git commit -m "feat(frontend): add ShareButton component with copy and revoke"
```

---

### Task 7: Integrar `ShareButton` en `/scan/[id]/page.tsx`

**Files:**
- Modify: `frontend/app/(app)/scan/[id]/page.tsx`

- [x] **Step 1: Agregar `ShareButton` al header del resultado**

En el componente que renderiza el resultado del scan, localizar el header/toolbar y agregar:

```tsx
import { ShareButton } from "@/components/scanner/ShareButton";

// Dentro del JSX del resultado (necesita `data.id` — el ID numérico de la DB, no el barcode):
{data?.db_id && (
  <ShareButton scanDbId={data.db_id} />
)}
```

**Nota:** La respuesta de `getScanResult()` devuelve `ScanResponse`. Si `ScanResponse` no incluye `db_id` (el ID numérico de la fila), agregar el campo:

En `backend/app/schemas/models.py`, en `ScanResponse`:
```python
db_id: int | None = None  # ID de ScanHistory — para operaciones de sharing
```

En `backend/app/routers/scan.py`, en el endpoint `GET /scan/result/{barcode}`, incluir `db_id` al construir la respuesta:
```python
response.db_id = scan_row.id
```

Si `_build_response()` no tiene acceso al row ID, agregar el parámetro.

- [x] **Step 2: Verificar TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "\[id\]/page"
```

Esperado: sin errores.

- [x] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/scan/\[id\]/page.tsx backend/app/schemas/models.py backend/app/routers/scan.py
git commit -m "feat(frontend): integrate ShareButton in scan result page"
```

---

### Task 8: Ruta pública `/scan/share/[token]`

**Files:**
- Create: `frontend/app/scan/share/[token]/page.tsx`

Esta ruta vive **fuera del route group `(app)`** — no tiene el auth guard del middleware.

- [x] **Step 1: Crear la carpeta y el archivo**

```bash
mkdir -p frontend/app/scan/share/\[token\]
```

- [x] **Step 2: Crear la página**

```tsx
// frontend/app/scan/share/[token]/page.tsx
import { getSharedScan } from "@/lib/api/scan";
import { ScanResultView } from "@/components/scanner/ScanResultView";
import { notFound } from "next/navigation";

interface SharedScanPageProps {
  params: { token: string };
}

export default async function SharedScanPage({ params }: SharedScanPageProps) {
  let scan;
  let expired = false;

  try {
    scan = await getSharedScan(params.token);
  } catch (err) {
    if ((err as Error).message === "EXPIRED") {
      expired = true;
    } else {
      notFound();
    }
  }

  if (expired) {
    return (
      <main className="flex min-h-screen items-center justify-center p-6">
        <div className="text-center space-y-2">
          <p className="text-lg font-semibold">Este link ha expirado</p>
          <p className="text-sm text-subtext">El propietario del scan puede generar uno nuevo.</p>
        </div>
      </main>
    );
  }

  if (!scan) notFound();

  return (
    <main className="min-h-screen bg-background">
      <div className="max-w-xl mx-auto px-4 py-6 space-y-4">
        {/* Badge de resultado compartido */}
        <div className="text-xs text-subtext font-mono text-center">
          Resultado compartido · expira {new Date(scan.scanned_at).toLocaleDateString("es-MX")}
        </div>

        {/* Reutilizar el componente de visualización en modo read-only.
            Sin ShareButton ni acceso al historial. */}
        <ScanResultView data={scan} readonly />
      </div>
    </main>
  );
}
```

**Nota:** `ScanResultView` es el componente de display del scan result. Si no existe como componente separado (actualmente puede estar inline en `/scan/[id]/page.tsx`), extraerlo primero como componente reutilizable.

Si la refactorización del componente es necesaria, hacerla en el mismo PR pero en un commit separado.

- [x] **Step 3: Verificar TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "share"
```

Esperado: sin errores.

- [x] **Step 4: Verificar que la ruta pública no tiene auth guard**

En `middleware.ts` o la config del middleware de Next.js, verificar que `/scan/share/` no está en la lista de rutas protegidas. El route group `(app)` ya debería excluir rutas fuera de él, pero confirmarlo:

```bash
grep -r "scan/share" frontend/middleware.ts frontend/app/middleware.ts 2>/dev/null || echo "No matcher encontrado — verificar middleware.ts"
```

Si hay un matcher que incluye `scan/*` globalmente, agregar excepción para `/scan/share/`.

- [x] **Step 5: Commit**

```bash
git add frontend/app/scan/share/
git commit -m "feat(frontend): add public shared scan route /scan/share/[token]"
```

---

### Task 9: Full test suite + lint + verificación E2E

- [x] **Step 1: Correr suite completa del backend**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Esperado: todos verdes.

- [x] **Step 2: Ruff + mypy**

```bash
cd backend && ruff check . && mypy app/ --ignore-missing-imports 2>&1 | tail -20
```

Esperado: sin errores.

- [x] **Step 3: TypeScript check completo**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -20
```

Esperado: sin errores.

- [x] **Step 4: Verificar que E2E existentes no tienen regresiones**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield && npx playwright test tests/specs/ --reporter=list 2>&1 | tail -20
```

Esperado: sin nuevas regresiones.

- [x] **Step 5: Commit final de cleanup**

```bash
git add -p
git commit -m "fix(scan-sharing): lint and type fixes"
```

---

## Verificación manual

1. Crear share como usuario A:
```bash
curl -X POST http://localhost:8000/scan/123/share \
  -H "Cookie: access_token=<jwt_user_a>"
# → {"share_url": "http://localhost:3000/scan/share/<token>", "expires_at": "..."}
```

2. Intentar crear share como usuario B:
```bash
curl -X POST http://localhost:8000/scan/123/share \
  -H "Cookie: access_token=<jwt_user_b>"
# → 403 Forbidden
```

3. Acceder al link sin cookie:
```bash
curl http://localhost:8000/scan/share/<token>
# → 200 con ScanShareProjection — sin user_id, sin share_token
```

4. Modificar `share_expires_at` a pasado en DB:
```bash
# UPDATE scan_history SET share_expires_at = '2020-01-01' WHERE share_token = '<token>';
curl http://localhost:8000/scan/share/<token>
# → 410 Gone
```

5. Revocar link:
```bash
curl -X DELETE http://localhost:8000/scan/123/share \
  -H "Cookie: access_token=<jwt_user_a>"
# → 204 No Content
curl http://localhost:8000/scan/share/<token>
# → 404 Not Found
```
