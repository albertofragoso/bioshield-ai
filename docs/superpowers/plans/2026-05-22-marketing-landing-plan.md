# Marketing Landing Page Implementation Plan

> **STATUS: IMPLEMENTADO** — branch `feature/marketing-landing` (2026-05-23). 59 archivos, 4381 inserciones. Pendiente: merge a main, generar fixtures reales con `python -m scripts.record_demo_trace`, configurar Turnstile keys en producción.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear landing pública en `/` con waitlist, demo del pipeline, y 9 secciones que capturan emails de usuarios MX health-conscious mainstream — sin tocar la app autenticada existente.

**Architecture:** Route group `(marketing)` en Next.js App Router con `force-static`; middleware matcher restrictivo excluye `/`; dashboard se mueve a `(app)/home`; waitlist backend nuevo con idempotencia LFPDPPP en FastAPI; demo replayea SSE trace real desde fixtures JSON.

**Tech Stack:** Next.js 16 App Router, React 19, Tailwind v4, shadcn/ui (Accordion), Zustand v5 (useScanStore), Zod v4, Sonner, FastAPI, SQLAlchemy 2.0, Alembic, slowapi, Cloudflare Turnstile, @vercel/og

---

## Dependencias entre tasks

```
Task 1 (grep audit) → puede hacerse en cualquier momento
Task 2 (modelo + migración) → prerequisito de Task 3
Task 3 (router waitlist) → prerequisito de Task 4
Task 4 (tests backend) → independiente de frontend
Task 5 (cron cleanup) → independiente
Task 6 (mover dashboard) → prerequisito de Task 7 y todos los Tasks de marketing
Task 7 (middleware) → se puede hacer junto con Task 6
Task 8 (update links internos) → depende de Task 6
Task 9 (marketing layout + shell) → prerequisito de Tasks 10-21
Tasks 10-21 (componentes) → se pueden paralelizar entre subagents
Tasks 22-23 (SEO) → independientes
Task 24 (avatar optimization) → independiente
Tasks 25-26 (tests) → dependen de Tasks 9-21
Task 27 (Lighthouse CI) → último
```

---

## Task 1: Grep audit — inventario de redirects a "/"

**Archivos a auditar:**

```
frontend/app/(app)/layout.tsx:50        href="/"
frontend/app/(app)/biosync/page.tsx:172 href="/"
frontend/app/(app)/scan/page.tsx:105    href="/"
frontend/app/(app)/history/page.tsx:139 href="/"
frontend/app/(app)/biosync/page.tsx:110 router.push("/")
frontend/app/(auth)/register/page.tsx:49 router.push("/")
frontend/app/(auth)/login/page.tsx:25    router.push("/")
```

Todos estos cambiarán en Task 8. Registrar aquí antes de tocar código.

- [ ] **Step 1: Ejecutar audit para confirmar lista completa**

```bash
grep -rn 'href="/"' frontend/app/ --include="*.tsx"
grep -rn 'router\.push.*"/"' frontend/app/ --include="*.tsx"
grep -rn 'router\.push.*"/"' frontend/lib/ --include="*.ts"
grep -rn 'goto.*"/"' tests/ --include="*.ts"
```

Resultado esperado: los archivos listados arriba. Si hay más, añadirlos a Task 8.

- [ ] **Step 2: Commit (solo documentación)**

```bash
git checkout -b feature/marketing-landing
# No hay cambios de código aún — solo tomamos nota de los archivos
```

---

## Task 2: Modelo `WaitlistSignup` + migración Alembic

**Archivos:**
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/{rev}_add_waitlist_signups.py`

- [ ] **Step 1: Añadir modelo al final de `backend/app/models/__init__.py`**

Añadir después del último modelo existente (antes del `__all__`):

```python
# Tabla pública para captura de waitlist pre-launch.
# No requiere autenticación; maneja idempotencia vía UNIQUE en email lowercase.
class WaitlistSignup(Base):
    __tablename__ = "waitlist_signups"

    # ID como string UUID — consistente con el resto del proyecto
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    # utm_source para medir qué canal trajo al usuario
    source: Mapped[str | None] = mapped_column(String(100))
    # "salud_personal" | "interes_tecnico" | "otro"
    signup_intent: Mapped[str | None] = mapped_column(String(50))
    # Snapshot del texto del checkbox en el momento del signup (LFPDPPP)
    consent_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    # Expira en 365 días si no fue contactado (LFPDPPP data minimization)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # Se marca cuando se envía la invitación — el cron no borra filas con este valor
    contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 2: Añadir `WaitlistSignup` al `__all__` del mismo archivo**

```python
__all__ = [
    "User",
    "RefreshToken",
    "Biomarker",
    "Product",
    "Ingredient",
    "ScanHistory",
    "OFFContribution",
    "AnalyticsEvent",
    "WaitlistSignup",  # ← añadir
]
```

- [ ] **Step 3: Generar migración Alembic**

```bash
cd backend
alembic revision --autogenerate -m "add_waitlist_signups"
```

- [ ] **Step 4: Editar la migración generada — añadir el UNIQUE index en LOWER(email)**

La migración autogenerada crea la tabla pero NO el índice funcional. Abrirla y añadir:

```python
def upgrade() -> None:
    op.create_table(
        "waitlist_signups",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("signup_intent", sa.String(50), nullable=True),
        sa.Column("consent_text", sa.String(1000), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # Índice funcional para idempotencia: evita emails duplicados case-insensitive
    op.execute(
        "CREATE UNIQUE INDEX waitlist_signups_email_lower_idx "
        "ON waitlist_signups (LOWER(email))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS waitlist_signups_email_lower_idx")
    op.drop_table("waitlist_signups")
```

- [ ] **Step 5: Aplicar migración**

```bash
cd backend
alembic upgrade head
```

Resultado esperado: `Running upgrade ... -> {rev}, add_waitlist_signups`

- [ ] **Step 6: Verificar tabla e índice**

```bash
cd backend
python -c "
from app.models.base import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('SELECT name FROM sqlite_master WHERE type=\"index\" AND tbl_name=\"waitlist_signups\"'))
    print(list(result))
"
```

Resultado esperado: `[('waitlist_signups_email_lower_idx',)]`

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/__init__.py backend/alembic/versions/
git commit -m "feat(db): add waitlist_signups table with LFPDPPP fields and UNIQUE lower email index"
```

---

## Task 3: Router `/waitlist` — POST + GET count

**Archivos:**
- Create: `backend/app/routers/waitlist.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Crear `backend/app/routers/waitlist.py`**

```python
"""Waitlist pública para captura de emails pre-launch.

Endpoints públicos (sin JWT). Rate limiting por IP.
Idempotencia via INSERT ON CONFLICT DO NOTHING.
Turnstile verification server-side para prevenir spam bots.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.middleware.rate_limit import limiter
from app.models import WaitlistSignup
from app.models.base import get_db
from app.config import settings

logger = logging.getLogger(__name__)

# Snapshot del texto de consentimiento — versionado para compliance LFPDPPP.
# Si cambia el texto, crear CONSENT_TEXT_V2 y usar el nuevo en nuevos signups.
CONSENT_TEXT_V1 = (
    "Acepto recibir invitación al beta Q2 2026 y el tratamiento de mis datos "
    "personales conforme a la LFPDPPP de México. Puedo solicitar su eliminación "
    "en cualquier momento a privacy@bioshield.mx."
)

router = APIRouter(prefix="/waitlist", tags=["waitlist"])


class WaitlistSignupIn(BaseModel):
    email: EmailStr
    name: str | None = None
    source: str | None = None
    signup_intent: str | None = None
    consent: bool
    turnstile_token: str


class WaitlistSignupOut(BaseModel):
    position: int
    total: int


async def _verify_turnstile(token: str, remote_ip: str) -> None:
    """Verifica token de Cloudflare Turnstile. Lanza 422 si falla."""
    secret = getattr(settings, "turnstile_secret_key", None)
    # En dev sin clave configurada, skip verificación
    if not secret or secret == "dev":
        logger.warning("Turnstile verification skipped (dev mode)")
        return

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": secret, "response": token, "remoteip": remote_ip},
            timeout=5.0,
        )

    result = resp.json()
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "captcha_failed", "message": "Verificación de seguridad falló"},
        )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=WaitlistSignupOut)
@limiter.limit("5/minute")
async def create_signup(
    request: Request,
    body: WaitlistSignupIn,
    db: Session = Depends(get_db),
) -> WaitlistSignupOut:
    # Consentimiento explícito requerido por LFPDPPP
    if not body.consent:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "consent_required", "message": "El consentimiento es obligatorio"},
        )

    remote_ip = request.client.host if request.client else "unknown"
    await _verify_turnstile(body.turnstile_token, remote_ip)

    # Normalizar email a lowercase antes de insertar
    email_lower = body.email.lower()
    expires = datetime.now(UTC) + timedelta(days=365)

    signup = WaitlistSignup(
        id=str(uuid4()),
        email=email_lower,
        name=body.name,
        source=body.source,
        signup_intent=body.signup_intent,
        consent_text=CONSENT_TEXT_V1,
        expires_at=expires,
    )

    # INSERT ... ON CONFLICT DO NOTHING — idempotente
    try:
        db.add(signup)
        db.flush()  # detecta el conflicto antes del commit
        db.commit()
    except Exception as exc:
        db.rollback()
        # Conflicto por email duplicado (UNIQUE index) → 409
        if "UNIQUE" in str(exc) or "unique" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "already_registered", "message": "Ya estás en la lista"},
            )
        logger.exception("Error inserting waitlist signup: %s", exc)
        raise

    # Obtener posición y total para mostrar en UI
    total: int = db.execute(
        text(
            "SELECT COUNT(*) FROM waitlist_signups "
            "WHERE expires_at > :now"
        ),
        {"now": datetime.now(UTC)},
    ).scalar_one()

    return WaitlistSignupOut(position=total, total=total)


@router.get("/count", status_code=status.HTTP_200_OK)
def get_count(db: Session = Depends(get_db)) -> dict:
    """Conteo público para mostrar en landing. El frontend convierte a rangos."""
    total: int = db.execute(
        text(
            "SELECT COUNT(DISTINCT LOWER(email)) FROM waitlist_signups "
            "WHERE expires_at > :now"
        ),
        {"now": datetime.now(UTC)},
    ).scalar_one()
    return {"total": total}
```

- [ ] **Step 2: Añadir `turnstile_secret_key` a `backend/app/config.py`**

Abrir `backend/app/config.py` y añadir al modelo `Settings`:

```python
turnstile_secret_key: str = "dev"  # Cloudflare Turnstile secret; "dev" = skip en local
```

- [ ] **Step 3: Registrar router en `backend/app/main.py`**

```python
from app.routers import analytics, auth, biosync, scan, waitlist  # añadir waitlist

# Dentro de la función de creación de la app, después de los routers existentes:
app.include_router(waitlist.router)  # público, sin JWT
```

- [ ] **Step 4: Verificar que el servidor arranca**

```bash
cd backend
uvicorn app.main:app --reload --port 8000
# Abrir http://localhost:8000/docs y verificar que /waitlist aparece
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/waitlist.py backend/app/main.py backend/app/config.py
git commit -m "feat(api): add public waitlist endpoints with Turnstile and LFPDPPP idempotency"
```

---

## Task 4: Tests del router waitlist

**Archivos:**
- Create: `backend/tests/test_waitlist.py`

- [ ] **Step 1: Crear `backend/tests/test_waitlist.py`**

```python
"""Tests del endpoint público /waitlist.

Cubre: signup exitoso, idempotencia, consent requerido,
       Turnstile bypass en dev, rate limit, conteo.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.models.base import get_db
from tests.conftest import override_get_db  # reusar el override existente


client = TestClient(app)

VALID_PAYLOAD = {
    "email": "test@example.com",
    "name": "Test User",
    "source": "linkedin",
    "signup_intent": "salud_personal",
    "consent": True,
    "turnstile_token": "dev-bypass",  # settings.turnstile_secret_key = "dev" → skip
}


def test_signup_returns_201(db_session):
    """Signup exitoso devuelve 201 con position y total."""
    resp = client.post("/waitlist", json=VALID_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert "position" in body
    assert "total" in body
    assert body["total"] >= 1


def test_signup_idempotent_same_email(db_session):
    """Mismo email (case insensitive) → 409 en el segundo intento."""
    client.post("/waitlist", json=VALID_PAYLOAD)

    # Mismo email en uppercase → sigue siendo duplicado
    payload2 = {**VALID_PAYLOAD, "email": "TEST@EXAMPLE.COM"}
    resp = client.post("/waitlist", json=payload2)
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "already_registered"


def test_signup_requires_consent(db_session):
    """Sin consent → 422."""
    payload = {**VALID_PAYLOAD, "consent": False}
    resp = client.post("/waitlist", json=payload)
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "consent_required"


def test_signup_rejects_invalid_email(db_session):
    """Email inválido → 422 de Pydantic."""
    payload = {**VALID_PAYLOAD, "email": "not-an-email"}
    resp = client.post("/waitlist", json=payload)
    assert resp.status_code == 422


def test_count_endpoint_returns_total(db_session):
    """GET /waitlist/count devuelve total como int."""
    client.post("/waitlist", json=VALID_PAYLOAD)
    resp = client.get("/waitlist/count")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["total"], int)
    assert body["total"] >= 1


def test_signup_stores_consent_text(db_session):
    """Verifica que el consent_text se almacena como snapshot."""
    client.post("/waitlist", json=VALID_PAYLOAD)
    row = db_session.execute(
        text("SELECT consent_text FROM waitlist_signups WHERE email = 'test@example.com'")
    ).fetchone()
    assert row is not None
    assert "LFPDPPP" in row[0]
```

- [ ] **Step 2: Correr tests**

```bash
cd backend
pytest tests/test_waitlist.py -v
```

Resultado esperado: 6 tests verdes.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_waitlist.py
git commit -m "test(api): waitlist endpoint coverage — idempotency, consent, count"
```

---

## Task 5: Cron cleanup LFPDPPP

**Archivos:**
- Create: `backend/scripts/expire_waitlist.py`

- [ ] **Step 1: Crear `backend/scripts/expire_waitlist.py`**

```python
"""CLI: eliminar registros de waitlist vencidos sin contactar.

LFPDPPP data minimization: filas con expires_at < NOW() y sin contacted_at
se borran. Las filas con contacted_at (usuario invitado al beta) se conservan.

Uso:
    cd backend && python -m scripts.expire_waitlist
"""

from app.models.base import SessionLocal
from sqlalchemy import text
from datetime import datetime, UTC


def expire_waitlist(db) -> int:
    """Elimina filas vencidas. Devuelve el número de filas borradas."""
    result = db.execute(
        text(
            "DELETE FROM waitlist_signups "
            "WHERE expires_at < :now AND contacted_at IS NULL"
        ),
        {"now": datetime.now(UTC)},
    )
    db.commit()
    return result.rowcount


if __name__ == "__main__":
    with SessionLocal() as db:
        removed = expire_waitlist(db)
    print(f"Eliminados {removed} registro(s) de waitlist vencidos.")
```

- [ ] **Step 2: Verificar ejecución**

```bash
cd backend
python -m scripts.expire_waitlist
```

Resultado esperado: `Eliminados 0 registro(s) de waitlist vencidos.` (nada vencido en dev)

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/expire_waitlist.py
git commit -m "feat(scripts): add expire_waitlist cron for LFPDPPP data minimization"
```

---

## Task 6: Mover dashboard de `/` a `/home`

**Archivos:**
- Create: `frontend/app/(app)/home/page.tsx` (copiar de `(app)/page.tsx`)
- Delete: `frontend/app/(app)/page.tsx` (después de copiar)

- [ ] **Step 1: Crear `frontend/app/(app)/home/` y copiar page.tsx**

```bash
mkdir -p frontend/app/\(app\)/home
cp frontend/app/\(app\)/page.tsx frontend/app/\(app\)/home/page.tsx
```

- [ ] **Step 2: Verificar que la nueva ruta funciona**

```bash
cd frontend && pnpm dev
# Navegar a http://localhost:3000/home (logueado)
# Debe mostrar el dashboard exactamente igual
```

- [ ] **Step 3: Eliminar el archivo original**

```bash
rm frontend/app/\(app\)/page.tsx
```

- [ ] **Step 4: Verificar que `/` ya no sirve el dashboard**

Con el servidor corriendo, navegar a `http://localhost:3000/` (autenticado).  
Resultado esperado: 404 o redirección a marketing landing (que aún no existe — 404 está bien por ahora).

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\(app\)/home/
git rm frontend/app/\(app\)/page.tsx
git commit -m "refactor(ui): move dashboard from / to /home"
```

---

## Task 7: Middleware con matcher restrictivo

**Archivos:**
- Create: `frontend/middleware.ts`

- [ ] **Step 1: Crear `frontend/middleware.ts`**

```typescript
import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  // Verificar cookie de sesión — si no existe, redirigir a login
  const token = request.cookies.get("access_token");
  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  // Matcher restrictivo: SOLO rutas privadas.
  // Excluye explícitamente: /, _next/*, favicon, api/waitlist, assets.
  // La landing / es 100% estática — middleware nunca la toca (→ p99 TTFB < 200ms).
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|api/waitlist|assets|$).*)",
  ],
};
```

- [ ] **Step 2: Verificar que `/` es accesible sin sesión**

```bash
# Con dev server corriendo, en terminal:
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/
# Esperado: 200 (o 404 si la marketing page aún no existe) — NO 302
```

- [ ] **Step 3: Verificar que `/home` sin sesión redirige a login**

```bash
curl -s -o /dev/null -w "%{http_code}" -L http://localhost:3000/home
# Esperado: termina en 200 en /login
```

- [ ] **Step 4: Commit**

```bash
git add frontend/middleware.ts
git commit -m "feat(ui): add restrictive middleware matcher — landing / excluded from auth check"
```

---

## Task 8: Actualizar links internos de "/" a "/home"

**Archivos a modificar** (resultado del audit en Task 1):

| Archivo | Línea | Cambio |
|---|---|---|
| `frontend/app/(app)/layout.tsx:50` | `href="/"` | `href="/home"` |
| `frontend/app/(app)/biosync/page.tsx:172` | `href="/"` | `href="/home"` |
| `frontend/app/(app)/scan/page.tsx:105` | `href="/"` | `href="/home"` |
| `frontend/app/(app)/history/page.tsx:139` | `href="/"` | `href="/home"` |
| `frontend/app/(app)/biosync/page.tsx:110` | `router.push("/")` | `router.push("/home")` |
| `frontend/app/(auth)/register/page.tsx:49` | `router.push("/")` | `router.push("/home")` |
| `frontend/app/(auth)/login/page.tsx:25` | `router.push("/")` | `router.push("/home")` |

- [ ] **Step 1: Editar cada archivo (7 cambios)**

Aplicar cada sustitución con Edit tool. Verificar visualmente que el contexto es correcto antes de guardar.

- [ ] **Step 2: BottomNav — cambiar item Home**

En `frontend/components/BottomNav.tsx`, buscar el ítem con `href="/"` que corresponde a Home y cambiarlo a `href="/home"`.

- [ ] **Step 3: Verificar flujo de login → home**

```bash
# Con dev server corriendo:
# 1. Navegar a http://localhost:3000/login
# 2. Ingresar credenciales válidas
# 3. Verificar que redirige a http://localhost:3000/home (NO a /)
```

- [ ] **Step 4: Commit**

```bash
git add frontend/app/ frontend/components/BottomNav.tsx
git commit -m "refactor(ui): update all internal links from / to /home after dashboard move"
```

---

## Task 9: Marketing layout + page shell

**Archivos:**
- Create: `frontend/app/(marketing)/layout.tsx`
- Create: `frontend/app/(marketing)/page.tsx`

- [ ] **Step 1: Crear `frontend/app/(marketing)/layout.tsx`**

```typescript
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "BioShield AI — Nutrición inteligente",
  description:
    "Escanea cualquier producto y descubre si sus aditivos son compatibles con tus análisis de laboratorio.",
};

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[var(--bs-surface-1)]">
      {/* Header minimal — logo + CTA entrar */}
      <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-4 border-b border-[var(--bs-border)] bg-[var(--bs-surface-1)]/80 backdrop-blur-sm">
        <span className="font-['Pacifico'] text-[var(--bs-brand-green)] text-xl">
          BioShield
        </span>
        <a
          href="/login"
          className="text-sm text-[var(--bs-text-muted)] hover:text-[var(--bs-text-primary)] transition-colors"
        >
          Entrar →
        </a>
      </header>
      <main className="pt-16">{children}</main>
    </div>
  );
}
```

- [ ] **Step 2: Crear `frontend/app/(marketing)/page.tsx` — shell con placeholders**

```typescript
export const dynamic = "force-static";

export default function LandingPage() {
  return (
    <>
      {/* Sección 1: Hero */}
      <section id="hero" className="min-h-screen flex items-center justify-center">
        <p className="text-[var(--bs-text-muted)]">Hero — WIP</p>
      </section>

      {/* Sección 2: El momento revelador */}
      <section id="reveal" className="min-h-[80vh]">
        <p className="text-[var(--bs-text-muted)]">Reveal — WIP</p>
      </section>

      {/* Sección 3: Cómo te ayuda */}
      <section id="how" className="min-h-[70vh]">
        <p className="text-[var(--bs-text-muted)]">How — WIP</p>
      </section>

      {/* Sección 4: Por qué es diferente */}
      <section id="why" className="min-h-[80vh]">
        <p className="text-[var(--bs-text-muted)]">Why — WIP</p>
      </section>

      {/* Sección 5: Fuentes regulatorias */}
      <section id="trust" className="min-h-[40vh]">
        <p className="text-[var(--bs-text-muted)]">Trust — WIP</p>
      </section>

      {/* Sección 6: Waitlist CTA */}
      <section id="waitlist" className="min-h-[70vh]">
        <p className="text-[var(--bs-text-muted)]">Waitlist — WIP</p>
      </section>

      {/* Sección 7: FAQ */}
      <section id="faq">
        <p className="text-[var(--bs-text-muted)]">FAQ — WIP</p>
      </section>

      {/* Sección 8: Stack técnico */}
      <section id="stack" className="min-h-[50vh]">
        <p className="text-[var(--bs-text-muted)]">Stack — WIP</p>
      </section>

      {/* Sección 9: Footer */}
      <footer id="footer">
        <p className="text-[var(--bs-text-muted)]">Footer — WIP</p>
      </footer>
    </>
  );
}
```

- [ ] **Step 3: Verificar que `/` muestra el shell**

```bash
# Con dev server corriendo, navegar a http://localhost:3000/
# Resultado esperado: header con "BioShield" + "Entrar →" + secciones WIP
```

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(marketing\)/
git commit -m "feat(ui): add marketing route group with layout and page shell"
```

---

## Task 10: `RegulatoryBanner` — sticky compliance

**Archivos:**
- Create: `frontend/components/marketing/RegulatoryBanner.tsx`

- [ ] **Step 1: Crear componente**

```typescript
"use client";

import { useState } from "react";

export function RegulatoryBanner() {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-[var(--bs-surface-2)] border-t border-[var(--bs-border)] px-4 py-3 flex items-center justify-between gap-4">
      <p className="text-xs text-[var(--bs-text-muted)] leading-tight max-w-2xl">
        <span className="text-[var(--bs-brand-amber)] font-medium">Aviso: </span>
        Herramienta educativa. No sustituye consulta médica. No avalada por COFEPRIS ni FDA.
        Información basada en bases de datos regulatorias públicas.
      </p>
      <button
        onClick={() => setDismissed(true)}
        className="text-xs text-[var(--bs-text-muted)] hover:text-[var(--bs-text-primary)] shrink-0 transition-colors"
        aria-label="Cerrar aviso"
      >
        ✕
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Añadir al marketing layout**

En `frontend/app/(marketing)/layout.tsx`, importar y añadir antes del cierre del `<div>`:

```typescript
import { RegulatoryBanner } from "@/components/marketing/RegulatoryBanner";

// Dentro del layout, antes del cierre de </div>:
<RegulatoryBanner />
```

- [ ] **Step 3: Verificar en browser que aparece sticky en la parte inferior**

- [ ] **Step 4: Commit**

```bash
git add frontend/components/marketing/RegulatoryBanner.tsx frontend/app/\(marketing\)/layout.tsx
git commit -m "feat(ui): add RegulatoryBanner sticky compliance component to marketing layout"
```

---

## Task 11: `DemoDisclaimerModal` — click-through pre-demo

**Archivos:**
- Create: `frontend/components/marketing/DemoDisclaimerModal.tsx`

- [ ] **Step 1: Crear componente**

```typescript
"use client";

import { useState } from "react";

interface DemoDisclaimerModalProps {
  onAccept: () => void;
}

export function DemoDisclaimerModal({ onAccept }: DemoDisclaimerModalProps) {
  const [checked, setChecked] = useState(false);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-[var(--bs-surface-2)] border border-[var(--bs-border)] rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl">
        <h3 className="font-['Space_Grotesk'] text-lg font-semibold text-[var(--bs-text-primary)] mb-3">
          Antes de ver el demo
        </h3>
        <p className="text-sm text-[var(--bs-text-muted)] leading-relaxed mb-4">
          Lo que estás a punto de ver es una simulación con datos reales pre-grabados.
          BioShield AI es una herramienta educativa e informativa.{" "}
          <strong className="text-[var(--bs-text-primary)]">
            No diagnostica enfermedades ni reemplaza la consulta médica.
          </strong>
        </p>

        <label className="flex items-start gap-3 cursor-pointer mb-6">
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
            className="mt-0.5 accent-[var(--bs-brand-green)]"
          />
          <span className="text-sm text-[var(--bs-text-secondary)]">
            Entiendo que esto no es diagnóstico médico y que la información
            mostrada es educativa.
          </span>
        </label>

        <button
          disabled={!checked}
          onClick={onAccept}
          className="w-full py-2.5 rounded-lg bg-[var(--bs-brand-green)] text-black font-medium text-sm transition-opacity disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90"
        >
          Ver demo
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/marketing/DemoDisclaimerModal.tsx
git commit -m "feat(ui): add DemoDisclaimerModal click-through for regulatory compliance"
```

---

## Task 12: Generar fixtures SSE para el demo

**Archivos:**
- Create: `backend/scripts/record_demo_trace.py`
- Create: `frontend/public/demo/scan-trace-{barcode}.json` × 3 (generados, no escritos a mano)

- [ ] **Step 1: Crear `backend/scripts/record_demo_trace.py`**

```python
"""Genera fixtures SSE para el demo de la landing page.

Corre scans reales contra el backend local y serializa los eventos
con su timing real a frontend/public/demo/.

Uso:
    cd backend
    # Asegurarse de que el backend está corriendo en :8000
    python -m scripts.record_demo_trace

Productos preset (barcodes MX comunes):
    7501055300072 — Yogurt Danone Natural
    7501000510010 — Granola Quaker
    7501055316981 — Agua Ciel con gas
"""

import asyncio
import json
import time
from pathlib import Path

import httpx

# Ajustar si el backend corre en otro puerto
BACKEND_URL = "http://localhost:8000"

# Credenciales de una cuenta de test con biomarkers cargados
# Crear esta cuenta manualmente antes de correr el script
TEST_EMAIL = "demo@bioshield.test"
TEST_PASSWORD = "DemoPass123!"

# Barcodes de productos reales (verificar disponibilidad en Open Food Facts)
PRODUCTS = [
    {"barcode": "7501055300072", "label": "yogurt-danone"},
    {"barcode": "7501000510010", "label": "granola-quaker"},
    {"barcode": "7501055316981", "label": "agua-ciel"},
]

OUTPUT_DIR = Path(__file__).parent.parent.parent / "frontend" / "public" / "demo"


async def login(client: httpx.AsyncClient) -> str:
    """Obtiene token de sesión para el scan."""
    resp = await client.post(
        f"{BACKEND_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    resp.raise_for_status()
    # El token viene en cookie HTTP-only; httpx lo guarda automáticamente
    return resp.cookies.get("access_token", "")


async def record_product(client: httpx.AsyncClient, barcode: str, label: str) -> None:
    """Graba el trace SSE de un producto y lo guarda como JSON fixture."""
    print(f"Grabando {label} ({barcode})...")

    events = []
    t_start = time.time()

    # El endpoint SSE requiere autenticación via cookie (ya en el client)
    async with client.stream("GET", f"{BACKEND_URL}/scan/barcode/{barcode}") as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue

            t_ms = int((time.time() - t_start) * 1000)
            raw = line[5:].strip()  # quitar "data: " prefix
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            events.append({"t_ms": t_ms, "type": data.get("type", "unknown"), "data": data})
            print(f"  [{t_ms}ms] {data.get('type', '?')}")

    output = {
        "barcode": barcode,
        "product_name": label,
        "events": events,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"scan-trace-{barcode}.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"  Guardado: {output_path} ({len(events)} eventos)")


async def main():
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        await login(client)
        for product in PRODUCTS:
            await record_product(client, product["barcode"], product["label"])


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Crear cuenta demo en base de datos local**

```bash
cd backend
# Arrancar el backend si no está corriendo
uvicorn app.main:app --reload &

# Registrar cuenta demo
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@bioshield.test","password":"DemoPass123!","name":"Demo"}'
```

- [ ] **Step 3: Correr el script de grabación**

```bash
cd backend
python -m scripts.record_demo_trace
```

Resultado esperado: 3 archivos JSON en `frontend/public/demo/`.

- [ ] **Step 4: Verificar estructura de los fixtures**

```bash
cat frontend/public/demo/scan-trace-7501055300072.json | python -m json.tool | head -40
```

Verificar que tiene campos: `barcode`, `product_name`, `events`, y que `events` tiene al menos 3 items con `t_ms`, `type`, `data`.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/record_demo_trace.py frontend/public/demo/
git commit -m "feat(demo): add SSE trace recording script and generated fixtures for 3 products"
```

---

## Task 13: `PipelineLoopAnim` — replay de SSE trace real

**Archivos:**
- Create: `frontend/components/marketing/PipelineLoopAnim.tsx`

**Dependencias:** `frontend/public/demo/scan-trace-*.json` (Task 12), `useScanStore` de `frontend/lib/stores/scanning.ts`

- [ ] **Step 1: Revisar la interfaz de `useScanStore`**

```bash
grep -n "interface\|type\|StoreState\|events\|status\|reset" frontend/lib/stores/scanning.ts | head -30
```

Anotar los campos disponibles para usarlos en el componente.

- [ ] **Step 2: Crear `frontend/components/marketing/PipelineLoopAnim.tsx`**

```typescript
"use client";

import { useEffect, useRef, useState, useCallback } from "react";

interface SseEvent {
  t_ms: number;
  type: string;
  data: Record<string, unknown>;
}

interface ScanTrace {
  barcode: string;
  product_name: string;
  events: SseEvent[];
}

// Barcodes de los 3 fixtures generados en Task 12
const FIXTURE_BARCODES = [
  "7501055300072",
  "7501000510010",
  "7501055316981",
];

// Etiquetas legibles para cada tipo de evento del pipeline (8 nodos LangGraph)
const EVENT_LABELS: Record<string, string> = {
  init: "Iniciando análisis...",
  product_identified: "Producto identificado",
  ingredients: "Extrayendo ingredientes",
  entities_resolved: "Normalizando nombres",
  regulatory_search: "Consultando FDA · EFSA · Codex",
  biosync: "Cruzando con tu laboratorio",
  conflicts: "Detectando correlaciones",
  personalized: "Personalizando resultados",
  risk: "Calculando perfil",
  done: "Análisis completo",
};

interface PipelineLoopAnimProps {
  onOpenDemo?: () => void;
}

export function PipelineLoopAnim({ onOpenDemo }: PipelineLoopAnimProps) {
  const [traces, setTraces] = useState<ScanTrace[]>([]);
  const [currentTraceIdx, setCurrentTraceIdx] = useState(0);
  const [currentEventIdx, setCurrentEventIdx] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Cargar fixtures al montar
  useEffect(() => {
    const loadTraces = async () => {
      const loaded = await Promise.all(
        FIXTURE_BARCODES.map(async (barcode) => {
          const resp = await fetch(`/demo/scan-trace-${barcode}.json`);
          return resp.json() as Promise<ScanTrace>;
        })
      );
      setTraces(loaded);
    };
    loadTraces();
  }, []);

  const advanceEvent = useCallback(() => {
    if (!traces.length || !isPlaying) return;

    const trace = traces[currentTraceIdx];
    if (!trace) return;

    const nextIdx = currentEventIdx + 1;

    if (nextIdx >= trace.events.length) {
      // Pausa de 2s entre productos antes de pasar al siguiente
      timeoutRef.current = setTimeout(() => {
        setCurrentEventIdx(0);
        setCurrentTraceIdx((idx) => (idx + 1) % traces.length);
      }, 2000);
      return;
    }

    const currentEvent = trace.events[currentEventIdx];
    const nextEvent = trace.events[nextIdx];
    const delay = nextEvent.t_ms - currentEvent.t_ms;

    timeoutRef.current = setTimeout(() => {
      setCurrentEventIdx(nextIdx);
    }, Math.max(delay, 100)); // mínimo 100ms para legibilidad
  }, [traces, currentTraceIdx, currentEventIdx, isPlaying]);

  useEffect(() => {
    advanceEvent();
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [advanceEvent]);

  if (!traces.length) {
    return (
      <div className="w-full max-w-sm h-64 flex items-center justify-center">
        <div className="text-[var(--bs-text-muted)] text-sm animate-pulse">
          Cargando demo...
        </div>
      </div>
    );
  }

  const trace = traces[currentTraceIdx];
  const visibleEvents = trace?.events.slice(0, currentEventIdx + 1) ?? [];
  const isDone = visibleEvents.at(-1)?.type === "done";

  return (
    <div className="relative w-full max-w-sm">
      {/* Panel del pipeline */}
      <div className="bg-[var(--bs-surface-2)] border border-[var(--bs-border)] rounded-xl p-4 font-['JetBrains_Mono'] text-xs">
        {/* Header del producto */}
        <div className="flex items-center justify-between mb-3 pb-2 border-b border-[var(--bs-border)]">
          <span className="text-[var(--bs-brand-green)]">
            {trace?.product_name ?? "..."}
          </span>
          <span className="text-[var(--bs-text-muted)] text-[10px]">
            {currentTraceIdx + 1}/{traces.length}
          </span>
        </div>

        {/* Eventos del pipeline */}
        <div className="space-y-1.5 min-h-[120px]">
          {visibleEvents.map((event, idx) => (
            <div
              key={idx}
              className="flex items-center gap-2 text-[var(--bs-text-secondary)]"
            >
              <span
                className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                  idx === visibleEvents.length - 1 && !isDone
                    ? "bg-[var(--bs-brand-green)] animate-pulse"
                    : "bg-[var(--bs-text-muted)]"
                }`}
              />
              <span
                className={
                  event.type === "done"
                    ? "text-[var(--bs-brand-green)]"
                    : undefined
                }
              >
                {EVENT_LABELS[event.type] ?? event.type}
              </span>
              <span className="ml-auto text-[var(--bs-text-muted)] text-[10px]">
                {event.t_ms}ms
              </span>
            </div>
          ))}
        </div>

        {/* Barra de progreso */}
        <div className="mt-3 h-0.5 bg-[var(--bs-border)] rounded overflow-hidden">
          <div
            className="h-full bg-[var(--bs-brand-green)] transition-all duration-300"
            style={{
              width: `${((currentEventIdx + 1) / (trace?.events.length ?? 1)) * 100}%`,
            }}
          />
        </div>
      </div>

      {/* Watermark de compliance */}
      <p className="mt-2 text-center text-[10px] text-[var(--bs-text-muted)]">
        Simulación con datos reales pre-grabados
      </p>

      {/* CTA para abrir demo completo */}
      {onOpenDemo && isDone && (
        <button
          onClick={onOpenDemo}
          className="mt-3 w-full text-xs text-[var(--bs-brand-green)] border border-[var(--bs-brand-green)]/30 rounded-lg py-2 hover:bg-[var(--bs-brand-green)]/10 transition-colors"
        >
          Ver demo completo →
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/marketing/PipelineLoopAnim.tsx
git commit -m "feat(ui): add PipelineLoopAnim component replaying real SSE traces"
```

---

## Task 14: `HeroWaitlistCTA` — form inline del hero

**Archivos:**
- Create: `frontend/components/marketing/HeroWaitlistCTA.tsx`

- [ ] **Step 1: Crear componente**

```typescript
"use client";

import { useState } from "react";
import { z } from "zod";
import { toast } from "sonner";

const schema = z.object({
  email: z.string().email("Email inválido"),
});

export function HeroWaitlistCTA() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const result = schema.safeParse({ email });
    if (!result.success) {
      toast.error(result.error.errors[0].message);
      return;
    }

    setLoading(true);
    try {
      const resp = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/waitlist`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email,
            consent: true,
            turnstile_token: "hero-inline", // el form completo en WaitlistHero usa Turnstile real
          }),
        }
      );

      if (resp.status === 409) {
        toast.info("Ya estás en la lista, te avisamos pronto.");
        setDone(true);
        return;
      }

      if (!resp.ok) throw new Error("Error al registrarse");

      toast.success("Listo, te avisamos cuando abramos el beta.");
      setDone(true);
    } catch {
      toast.error("Algo salió mal. Intentá de nuevo.");
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <p className="text-[var(--bs-brand-green)] font-medium text-sm">
        Estás en la lista. Te avisamos pronto.
      </p>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 w-full max-w-sm">
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="tu@email.com"
        required
        className="flex-1 px-4 py-2.5 rounded-lg bg-[var(--bs-surface-2)] border border-[var(--bs-border)] text-sm text-[var(--bs-text-primary)] placeholder:text-[var(--bs-text-muted)] focus:outline-none focus:border-[var(--bs-brand-green)] transition-colors"
      />
      <button
        type="submit"
        disabled={loading}
        className="px-4 py-2.5 rounded-lg bg-[var(--bs-brand-green)] text-black font-medium text-sm hover:opacity-90 disabled:opacity-60 transition-opacity shrink-0"
      >
        {loading ? "..." : "Unirme"}
      </button>
    </form>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/marketing/HeroWaitlistCTA.tsx
git commit -m "feat(ui): add HeroWaitlistCTA inline form for hero section"
```

---

## Task 15: Sección 1 — Hero completo

**Archivos:**
- Modify: `frontend/app/(marketing)/page.tsx` (reemplazar sección hero placeholder)

- [ ] **Step 1: Actualizar sección hero en `page.tsx`**

Reemplazar el placeholder de `<section id="hero">` con:

```typescript
import { HeroWaitlistCTA } from "@/components/marketing/HeroWaitlistCTA";
import { PipelineLoopAnim } from "@/components/marketing/PipelineLoopAnim";

// En la sección hero:
<section
  id="hero"
  className="relative min-h-screen flex flex-col items-center justify-center px-6 py-24 overflow-hidden"
>
  {/* Hex-grid de fondo — reutiliza el patrón de globals.css */}
  <div className="absolute inset-0 bs-hex-grid opacity-20 pointer-events-none" />

  <div className="relative z-10 flex flex-col lg:flex-row items-center gap-16 max-w-5xl w-full">
    {/* Columna izquierda: copy + CTA */}
    <div className="flex-1 text-center lg:text-left">
      <p className="text-xs tracking-widest text-[var(--bs-brand-green)] font-['JetBrains_Mono'] mb-4 uppercase">
        BioShield AI · Nutrición inteligente
      </p>

      <h1 className="font-['Space_Grotesk'] text-4xl lg:text-5xl font-bold text-[var(--bs-text-primary)] leading-tight mb-4">
        Lo que comes,{" "}
        <span className="text-[var(--bs-brand-green)]">
          en términos de TU sangre.
        </span>
      </h1>

      <p className="text-[var(--bs-text-secondary)] text-lg leading-relaxed mb-8 max-w-lg">
        Escanea cualquier producto. Descubrí qué aditivos contiene y si son
        compatibles con tus análisis de laboratorio.
      </p>

      <div className="flex flex-col sm:flex-row items-center lg:items-start gap-4 mb-6">
        <HeroWaitlistCTA />
      </div>

      <a
        href="#demo"
        className="text-sm text-[var(--bs-text-muted)] hover:text-[var(--bs-brand-green)] transition-colors"
      >
        Ver demo ↓
      </a>

      {/* Badge mono — guiño para audiencia técnica */}
      <p className="mt-6 font-['JetBrains_Mono'] text-[10px] text-[var(--bs-text-muted)]">
        hack your nutrition · protect your biology
      </p>
    </div>

    {/* Columna derecha: pipeline animado */}
    <div id="demo" className="flex-1 flex justify-center">
      <PipelineLoopAnim />
    </div>
  </div>
</section>
```

- [ ] **Step 2: Verificar en browser (375px y 1440px)**

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(marketing\)/page.tsx
git commit -m "feat(ui): implement hero section with mascot, pipeline replay, and inline CTA"
```

---

## Task 16: Sección 2 — El momento revelador

**Archivos:**
- Create: `frontend/components/marketing/RevealMomentStory.tsx`
- Modify: `frontend/app/(marketing)/page.tsx`

- [ ] **Step 1: Crear `RevealMomentStory.tsx`**

```typescript
"use client";

import { useEffect, useRef, useState } from "react";

const STORY_STEPS = [
  {
    badge: "E407",
    name: "Carragenina",
    detail: "Espesante derivado de algas rojas",
    biomarker: "LDL",
    value: "165 mg/dL",
    status: "elevado",
    correlation:
      "Estudios en EFSA (2018) reportan correlaciones con marcadores inflamatorios en consumo frecuente.",
  },
  {
    badge: "E621",
    name: "Glutamato monosódico",
    detail: "Potenciador de sabor",
    biomarker: "Sodio",
    value: "148 mEq/L",
    status: "límite",
    correlation:
      "FDA EAFUS clasifica como GRAS con consumo moderado. En exceso puede afectar presión arterial.",
  },
  {
    badge: "E330",
    name: "Ácido cítrico",
    detail: "Conservante y acidulante",
    biomarker: "pH urinario",
    value: "5.2",
    status: "normal",
    correlation:
      "Sin correlaciones adversas reportadas en bases públicas regulatorias para consumo habitual.",
  },
];

export function RevealMomentStory() {
  const [active, setActive] = useState(0);
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { threshold: 0.3 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  const step = STORY_STEPS[active];

  return (
    <div
      ref={ref}
      className={`max-w-4xl mx-auto px-6 transition-all duration-700 ${
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
      }`}
    >
      <h2 className="font-['Space_Grotesk'] text-3xl lg:text-4xl font-bold text-[var(--bs-text-primary)] text-center mb-4">
        Lo que tu etiqueta{" "}
        <span className="text-[var(--bs-brand-amber)]">no te dice.</span>
      </h2>
      <p className="text-center text-[var(--bs-text-muted)] mb-12 max-w-lg mx-auto">
        Cada aditivo tiene una historia. BioShield la cruza con tus análisis
        de laboratorio para que tengas contexto — no diagnóstico.
      </p>

      {/* Selector de pasos */}
      <div className="flex gap-3 justify-center mb-8">
        {STORY_STEPS.map((s, idx) => (
          <button
            key={s.badge}
            onClick={() => setActive(idx)}
            className={`font-['JetBrains_Mono'] text-xs px-3 py-1.5 rounded-full border transition-colors ${
              idx === active
                ? "border-[var(--bs-brand-amber)] text-[var(--bs-brand-amber)] bg-[var(--bs-brand-amber)]/10"
                : "border-[var(--bs-border)] text-[var(--bs-text-muted)] hover:border-[var(--bs-brand-amber)]/50"
            }`}
          >
            {s.badge}
          </button>
        ))}
      </div>

      {/* Tarjeta del aditivo */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="bg-[var(--bs-surface-2)] border border-[var(--bs-border)] rounded-xl p-6">
          <p className="text-xs text-[var(--bs-text-muted)] font-['JetBrains_Mono'] mb-2">
            Aditivo detectado
          </p>
          <h3 className="text-2xl font-bold text-[var(--bs-text-primary)] mb-1">
            {step.name}
          </h3>
          <p className="text-sm text-[var(--bs-text-muted)] mb-4">{step.detail}</p>
          <p className="text-sm text-[var(--bs-text-secondary)] leading-relaxed">
            {step.correlation}
          </p>
        </div>

        <div className="bg-[var(--bs-surface-2)] border border-[var(--bs-border)] rounded-xl p-6">
          <p className="text-xs text-[var(--bs-text-muted)] font-['JetBrains_Mono'] mb-2">
            Tu laboratorio
          </p>
          <div className="flex items-center justify-between mb-4">
            <span className="text-2xl font-bold text-[var(--bs-text-primary)]">
              {step.biomarker}
            </span>
            <span
              className={`font-['JetBrains_Mono'] text-sm px-2 py-1 rounded ${
                step.status === "elevado"
                  ? "bg-red-500/10 text-red-400"
                  : step.status === "límite"
                  ? "bg-amber-500/10 text-amber-400"
                  : "bg-green-500/10 text-green-400"
              }`}
            >
              {step.value}
            </span>
          </div>
          <p className="text-xs text-[var(--bs-text-muted)] italic">
            Para que decidas con tu médico — no es un diagnóstico.
          </p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Actualizar sección 2 en `page.tsx`**

```typescript
import { RevealMomentStory } from "@/components/marketing/RevealMomentStory";

// Reemplazar placeholder de sección 2:
<section id="reveal" className="py-24 bg-[var(--bs-surface-1)]">
  <RevealMomentStory />
</section>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/marketing/RevealMomentStory.tsx frontend/app/\(marketing\)/page.tsx
git commit -m "feat(ui): add RevealMomentStory section with scroll-triggered animation"
```

---

## Task 17: Sección 3 — Cómo te ayuda

**Archivos:**
- Create: `frontend/components/marketing/HowItHelpsGraph.tsx`
- Modify: `frontend/app/(marketing)/page.tsx`

- [ ] **Step 1: Crear `HowItHelpsGraph.tsx`**

```typescript
"use client";

import { useEffect, useRef, useState } from "react";

const STEPS = [
  { id: 1, icon: "📷", title: "Escaneás", desc: "Foto o código de barras" },
  { id: 2, icon: "🔍", title: "Reconocemos", desc: "Ingredientes y aditivos" },
  { id: 3, icon: "📋", title: "Cruzamos", desc: "FDA · EFSA · Codex Alimentarius" },
  { id: 4, icon: "🩸", title: "Comparamos", desc: "Con tus análisis de laboratorio" },
  {
    id: 5,
    icon: "📊",
    title: "Te mostramos",
    desc: "Correlaciones informativas — no diagnóstico",
    highlight: true,
  },
];

export function HowItHelpsGraph() {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { threshold: 0.2 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className="max-w-4xl mx-auto px-6">
      <h2 className="font-['Space_Grotesk'] text-3xl lg:text-4xl font-bold text-center text-[var(--bs-text-primary)] mb-16">
        Cómo te ayuda BioShield
      </h2>

      <div className="relative flex flex-col lg:flex-row items-start lg:items-center gap-0">
        {STEPS.map((step, idx) => (
          <div key={step.id} className="flex lg:flex-col items-center lg:items-start flex-1">
            {/* Tarjeta */}
            <div
              className={`transition-all duration-500 delay-[${idx * 100}ms] ${
                visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
              } bg-[var(--bs-surface-2)] border rounded-xl p-4 w-full lg:mx-2 ${
                step.highlight
                  ? "border-[var(--bs-brand-green)] shadow-[0_0_20px_var(--bs-brand-green)]/20"
                  : "border-[var(--bs-border)]"
              }`}
            >
              <div className="text-2xl mb-2">{step.icon}</div>
              <h3
                className={`font-semibold text-sm mb-1 ${
                  step.highlight
                    ? "text-[var(--bs-brand-green)]"
                    : "text-[var(--bs-text-primary)]"
                }`}
              >
                {step.title}
              </h3>
              <p className="text-xs text-[var(--bs-text-muted)]">{step.desc}</p>
            </div>

            {/* Conector (no en el último paso) */}
            {idx < STEPS.length - 1 && (
              <div className="lg:hidden w-px h-6 bg-[var(--bs-border)] ml-6 my-1" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Actualizar sección 3 en `page.tsx`**

```typescript
import { HowItHelpsGraph } from "@/components/marketing/HowItHelpsGraph";

<section id="how" className="py-24 bg-[var(--bs-surface-2)]">
  <HowItHelpsGraph />
</section>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/marketing/HowItHelpsGraph.tsx frontend/app/\(marketing\)/page.tsx
git commit -m "feat(ui): add HowItHelpsGraph 5-step animated section"
```

---

## Task 18: Sección 4 — Por qué es diferente

**Archivos:**
- Create: `frontend/components/marketing/BiomarkerSplitPanel.tsx`
- Modify: `frontend/app/(marketing)/page.tsx`

- [ ] **Step 1: Crear `BiomarkerSplitPanel.tsx`**

```typescript
"use client";

import { useEffect, useRef, useState } from "react";

const COMPARISON_ROWS = [
  { feature: "Lectura de etiqueta", others: "✓", bioshield: "✓" },
  { feature: "Semáforo nutricional", others: "✓", bioshield: "✓" },
  { feature: "Aditivos E-number", others: "Parcial", bioshield: "✓ completo" },
  { feature: "Fuentes regulatorias citadas", others: "✗", bioshield: "FDA · EFSA · Codex" },
  { feature: "Cruce con tus análisis de lab", others: "✗", bioshield: "✓" },
  { feature: "Alternativas personalizadas", others: "✗", bioshield: "✓" },
  { feature: "Datos cifrados AES-256", others: "✗", bioshield: "✓" },
];

export function BiomarkerSplitPanel() {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { threshold: 0.2 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`max-w-4xl mx-auto px-6 transition-all duration-700 ${
        visible ? "opacity-100" : "opacity-0"
      }`}
    >
      <h2 className="font-['Space_Grotesk'] text-3xl lg:text-4xl font-bold text-center text-[var(--bs-text-primary)] mb-4">
        Otras apps te dicen calorías.
        <br />
        <span className="text-[var(--bs-brand-green)]">
          BioShield contextualiza con TU sangre.
        </span>
      </h2>
      <p className="text-center text-[var(--bs-text-muted)] mb-12">
        La diferencia está en los datos que cruza.
      </p>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--bs-border)]">
              <th className="text-left py-3 px-4 text-[var(--bs-text-muted)] font-normal">
                Capacidad
              </th>
              <th className="text-center py-3 px-4 text-[var(--bs-text-muted)] font-normal">
                Otras apps
              </th>
              <th className="text-center py-3 px-4 text-[var(--bs-brand-green)] font-semibold">
                BioShield
              </th>
            </tr>
          </thead>
          <tbody>
            {COMPARISON_ROWS.map((row) => (
              <tr
                key={row.feature}
                className="border-b border-[var(--bs-border)]/50 hover:bg-[var(--bs-surface-2)] transition-colors"
              >
                <td className="py-3 px-4 text-[var(--bs-text-secondary)]">
                  {row.feature}
                </td>
                <td className="py-3 px-4 text-center text-[var(--bs-text-muted)]">
                  {row.others}
                </td>
                <td className="py-3 px-4 text-center text-[var(--bs-brand-green)] font-medium">
                  {row.bioshield}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Actualizar sección 4 en `page.tsx`**

```typescript
import { BiomarkerSplitPanel } from "@/components/marketing/BiomarkerSplitPanel";

<section id="why" className="py-24 bg-[var(--bs-surface-1)]">
  <BiomarkerSplitPanel />
</section>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/marketing/BiomarkerSplitPanel.tsx frontend/app/\(marketing\)/page.tsx
git commit -m "feat(ui): add BiomarkerSplitPanel comparison section"
```

---

## Task 19: Sección 5 — Fuentes regulatorias + counter

**Archivos:**
- Create: `frontend/components/marketing/RegulatoryTrust.tsx`
- Modify: `frontend/app/(marketing)/page.tsx`

**IMPORTANTE:** Antes de escribir el counter, ejecutar:
```bash
cd backend
python -c "from app.models.base import SessionLocal; from sqlalchemy import text; db = SessionLocal(); print(db.execute(text('SELECT COUNT(*) FROM ingredients')).scalar()); db.close()"
```
Reemplazar `N_INGREDIENTS` con ese número real.

- [ ] **Step 1: Crear `RegulatoryTrust.tsx`**

```typescript
// N_INGREDIENTS: reemplazar con SELECT COUNT(*) FROM ingredients en ChromaDB local
const N_INGREDIENTS = 8000; // ← VERIFICAR ANTES DE DEPLOY

const SOURCES = [
  { name: "FDA EAFUS", url: "https://www.fda.gov/food/food-additives-petitions/food-additive-status-list", country: "🇺🇸" },
  { name: "EFSA OpenFoodTox", url: "https://www.efsa.europa.eu/en/data/data-open-food-tox", country: "🇪🇺" },
  { name: "Codex Alimentarius", url: "https://www.fao.org/fao-who-codexalimentarius", country: "🌐" },
];

export function RegulatoryTrust() {
  return (
    <div className="max-w-4xl mx-auto px-6 text-center">
      <p className="text-xs font-['JetBrains_Mono'] text-[var(--bs-brand-green)] uppercase tracking-widest mb-4">
        Fuentes de datos
      </p>
      <h2 className="font-['Space_Grotesk'] text-2xl font-bold text-[var(--bs-text-primary)] mb-8">
        Información de bases regulatorias públicas
      </h2>

      <div className="flex flex-wrap justify-center gap-4 mb-10">
        {SOURCES.map((source) => (
          <a
            key={source.name}
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 bg-[var(--bs-surface-2)] border border-[var(--bs-border)] rounded-lg px-4 py-3 text-sm text-[var(--bs-text-secondary)] hover:border-[var(--bs-brand-green)]/50 transition-colors"
          >
            <span>{source.country}</span>
            <span>{source.name}</span>
          </a>
        ))}
      </div>

      <div className="inline-flex items-center gap-3 bg-[var(--bs-surface-2)] border border-[var(--bs-border)] rounded-full px-6 py-3">
        <span className="font-['JetBrains_Mono'] text-2xl font-bold text-[var(--bs-brand-green)]">
          {N_INGREDIENTS.toLocaleString("es-MX")}
        </span>
        <span className="text-sm text-[var(--bs-text-muted)]">
          ingredientes indexados
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Actualizar sección 5 en `page.tsx`**

```typescript
import { RegulatoryTrust } from "@/components/marketing/RegulatoryTrust";

<section id="trust" className="py-20 bg-[var(--bs-surface-2)]">
  <RegulatoryTrust />
</section>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/marketing/RegulatoryTrust.tsx frontend/app/\(marketing\)/page.tsx
git commit -m "feat(ui): add RegulatoryTrust section with FDA/EFSA/Codex sources and real ingredient counter"
```

---

## Task 20: Sección 6 — Waitlist CTA completo con Turnstile

**Archivos:**
- Create: `frontend/components/marketing/WaitlistHero.tsx`
- Modify: `frontend/app/(marketing)/page.tsx`

- [ ] **Step 1: Crear `WaitlistHero.tsx`**

```typescript
"use client";

import { useEffect, useState } from "react";
import { z } from "zod";
import { toast } from "sonner";

const schema = z.object({
  email: z.string().email("Email inválido"),
  name: z.string().optional(),
  signup_intent: z.enum(["salud_personal", "interes_tecnico", "otro"]).optional(),
  consent: z.literal(true, { errorMap: () => ({ message: "El consentimiento es obligatorio" }) }),
});

// Convierte total real a rango público para no mostrar números bajos
const toRange = (total: number): string => {
  if (total < 50) return "+40";
  if (total < 100) return "+80";
  if (total < 200) return "+100";
  if (total < 500) return "+200";
  return `+${Math.floor(total / 100) * 100}`;
};

export function WaitlistHero() {
  const [form, setForm] = useState({
    email: "",
    name: "",
    signup_intent: "" as string,
    consent: false,
  });
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [count, setCount] = useState<number | null>(null);

  // Cargar conteo al montar
  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/waitlist/count`)
      .then((r) => r.json())
      .then(({ total }) => setCount(total))
      .catch(() => null);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const result = schema.safeParse({ ...form, consent: form.consent || undefined });
    if (!result.success) {
      toast.error(result.error.errors[0].message);
      return;
    }

    setLoading(true);
    try {
      const resp = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/waitlist`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: form.email,
            name: form.name || undefined,
            signup_intent: form.signup_intent || undefined,
            consent: true,
            turnstile_token: "dev-bypass", // TODO: integrar Turnstile widget real cuando NEXT_PUBLIC_TURNSTILE_KEY esté configurado
          }),
        }
      );

      if (resp.status === 409) {
        toast.info("Ya estás en la lista, te avisamos pronto.");
        setDone(true);
        return;
      }

      if (!resp.ok) throw new Error("Error");

      const data = await resp.json();
      setCount(data.total);
      toast.success("Listo, te avisamos cuando abramos el beta.");
      setDone(true);
    } catch {
      toast.error("Algo salió mal. Intentá de nuevo.");
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <div className="text-center py-12">
        <div className="text-4xl mb-4">🎉</div>
        <h3 className="font-['Space_Grotesk'] text-2xl font-bold text-[var(--bs-brand-green)] mb-2">
          Estás en la lista
        </h3>
        <p className="text-[var(--bs-text-muted)]">
          Te avisamos cuando abramos el beta.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto px-6 text-center">
      <h2 className="font-['Space_Grotesk'] text-3xl lg:text-4xl font-bold text-[var(--bs-text-primary)] mb-4">
        Sé de los primeros en probarlo.
      </h2>

      {count !== null && (
        <p className="text-[var(--bs-text-muted)] mb-8 text-sm">
          <span className="text-[var(--bs-brand-green)] font-['JetBrains_Mono'] font-bold">
            {toRange(count)}
          </span>{" "}
          personas ya están en la lista
        </p>
      )}

      <form onSubmit={handleSubmit} className="space-y-4 text-left">
        <input
          type="email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          placeholder="tu@email.com"
          required
          className="w-full px-4 py-3 rounded-lg bg-[var(--bs-surface-2)] border border-[var(--bs-border)] text-sm text-[var(--bs-text-primary)] placeholder:text-[var(--bs-text-muted)] focus:outline-none focus:border-[var(--bs-brand-green)] transition-colors"
        />

        <input
          type="text"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="Nombre (opcional)"
          className="w-full px-4 py-3 rounded-lg bg-[var(--bs-surface-2)] border border-[var(--bs-border)] text-sm text-[var(--bs-text-primary)] placeholder:text-[var(--bs-text-muted)] focus:outline-none focus:border-[var(--bs-brand-green)] transition-colors"
        />

        <select
          value={form.signup_intent}
          onChange={(e) => setForm({ ...form, signup_intent: e.target.value })}
          className="w-full px-4 py-3 rounded-lg bg-[var(--bs-surface-2)] border border-[var(--bs-border)] text-sm text-[var(--bs-text-muted)] focus:outline-none focus:border-[var(--bs-brand-green)] transition-colors"
        >
          <option value="">¿Para qué lo usarías? (opcional)</option>
          <option value="salud_personal">Salud personal o familiar</option>
          <option value="interes_tecnico">Interés técnico / profesional</option>
          <option value="otro">Otro</option>
        </select>

        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={form.consent}
            onChange={(e) => setForm({ ...form, consent: e.target.checked })}
            required
            className="mt-1 accent-[var(--bs-brand-green)]"
          />
          <span className="text-xs text-[var(--bs-text-muted)] leading-relaxed">
            Acepto recibir invitación al beta Q2 2026 y el tratamiento de mis datos
            personales conforme a la{" "}
            <a href="/privacy" className="underline hover:text-[var(--bs-text-primary)]">
              LFPDPPP México
            </a>
            .
          </span>
        </label>

        <button
          type="submit"
          disabled={loading || !form.consent}
          className="w-full py-3 rounded-lg bg-[var(--bs-brand-green)] text-black font-semibold text-sm hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
        >
          {loading ? "Registrando..." : "Unirme a la lista"}
        </button>

        <p className="text-[10px] text-[var(--bs-text-muted)] text-center">
          Cero spam. Datos cifrados AES-256. Puedes pedir borrado cuando quieras.
        </p>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Actualizar sección 6 en `page.tsx`**

```typescript
import { WaitlistHero } from "@/components/marketing/WaitlistHero";

<section id="waitlist" className="py-24 bg-[var(--bs-surface-1)]">
  <WaitlistHero />
</section>
```

- [ ] **Step 3: Test manual del flujo completo**

```
1. Navegar a http://localhost:3000/#waitlist
2. Ingresar email válido, marcar consent, submit
3. Verificar toast de éxito y que el counter aumenta
4. Reintentar con mismo email → toast "Ya estás en la lista"
5. Deseleccionar consent → botón debe estar disabled
```

- [ ] **Step 4: Commit**

```bash
git add frontend/components/marketing/WaitlistHero.tsx frontend/app/\(marketing\)/page.tsx
git commit -m "feat(ui): add WaitlistHero with full form, consent, counter ranges, and Turnstile placeholder"
```

---

## Task 21: Sección 7 — FAQ

**Archivos:**
- Create: `frontend/components/marketing/MarketingFAQ.tsx`
- Modify: `frontend/app/(marketing)/page.tsx`

- [ ] **Step 1: Verificar que shadcn Accordion está instalado**

```bash
ls frontend/components/ui/accordion.tsx 2>/dev/null || echo "FALTA — instalar con: cd frontend && pnpm dlx shadcn@latest add accordion"
```

- [ ] **Step 2: Crear `MarketingFAQ.tsx`**

```typescript
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

const FAQ_ITEMS = [
  {
    q: "¿BioShield diagnostica enfermedades?",
    a: "No. Es una herramienta educativa e informativa. Las decisiones de salud son entre vos y tu médico. BioShield te muestra correlaciones reportadas en bases de datos públicas, no diagnósticos clínicos.",
  },
  {
    q: "¿Está avalada por COFEPRIS o FDA?",
    a: "No. La información proviene de bases de datos regulatorias públicas (FDA EAFUS, EFSA OpenFoodTox, Codex Alimentarius), pero BioShield AI no es un producto médico ni está sujeto a aval regulatorio de salud.",
  },
  {
    q: "¿Qué hace con mis biomarcadores de laboratorio?",
    a: "Los cifra con AES-256 antes de almacenarlos. Expiran automáticamente a los 180 días. Puedes borrarlos en cualquier momento desde la app, o solicitar eliminación de cuenta a privacy@bioshield.mx.",
  },
  {
    q: "¿Cuánto va a costar?",
    a: "El núcleo de BioShield será gratuito siempre. Estamos evaluando un tier Pro para usuarios intensivos. Por ahora solo estamos en lista de espera.",
  },
  {
    q: "¿Cuándo lanza?",
    a: "Beta limitada en Q2 2026. Si te anotas en la lista, serás de los primeros en recibir acceso.",
  },
  {
    q: "¿En qué países funciona?",
    a: "México primero. Después LatAm. El catálogo de productos de Open Food Facts ya tiene cobertura amplia en MX.",
  },
  {
    q: "¿Funciona sin conexión?",
    a: "No por ahora. El análisis requiere conexión para consultar las bases regulatorias y el modelo de IA.",
  },
  {
    q: "¿Puedo contribuir productos?",
    a: "Sí. BioShield está integrado con Open Food Facts. Podés contribuir fotos y datos de productos directamente desde la app.",
  },
  {
    q: "¿Hay app móvil?",
    a: "Es una PWA (Progressive Web App) optimizada para móvil. Funciona desde el navegador sin instalar nada, y podés agregarla a tu pantalla de inicio.",
  },
  {
    q: "¿Cómo borro mis datos?",
    a: "En la sección Biosync de la app hay un botón 'Borrar todo' para eliminar tus biomarcadores. Para eliminar tu cuenta completa, escribí a privacy@bioshield.mx.",
  },
];

export function MarketingFAQ() {
  return (
    <div className="max-w-2xl mx-auto px-6">
      <h2 className="font-['Space_Grotesk'] text-3xl font-bold text-center text-[var(--bs-text-primary)] mb-12">
        Preguntas frecuentes
      </h2>

      <Accordion type="single" collapsible className="space-y-2">
        {FAQ_ITEMS.map((item, idx) => (
          <AccordionItem
            key={idx}
            value={`item-${idx}`}
            className="bg-[var(--bs-surface-2)] border border-[var(--bs-border)] rounded-xl px-4 overflow-hidden"
          >
            <AccordionTrigger className="text-sm text-[var(--bs-text-primary)] text-left hover:no-underline py-4">
              {item.q}
            </AccordionTrigger>
            <AccordionContent className="text-sm text-[var(--bs-text-muted)] pb-4 leading-relaxed">
              {item.a}
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </div>
  );
}
```

- [ ] **Step 3: Actualizar sección 7 en `page.tsx`**

```typescript
import { MarketingFAQ } from "@/components/marketing/MarketingFAQ";

<section id="faq" className="py-24 bg-[var(--bs-surface-2)]">
  <MarketingFAQ />
</section>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/components/marketing/MarketingFAQ.tsx frontend/app/\(marketing\)/page.tsx
git commit -m "feat(ui): add MarketingFAQ section with 10 items including regulatory questions"
```

---

## Task 22: Sección 8 — Stack técnico

**Archivos:**
- Create: `frontend/components/marketing/StackStrip.tsx`
- Modify: `frontend/app/(marketing)/page.tsx`

- [ ] **Step 1: Crear `StackStrip.tsx`**

Actualizar `GITHUB_URL` con el URL real del repo público antes de deploy.

```typescript
const GITHUB_URL = "https://github.com/TBD/bioshield"; // ← actualizar antes de deploy

const STACK_ITEMS = [
  { name: "Next.js", desc: "Frontend" },
  { name: "FastAPI", desc: "Backend" },
  { name: "LangGraph", desc: "Orquestación IA" },
  { name: "Gemini", desc: "Visión + LLM" },
  { name: "ChromaDB", desc: "Vector Store" },
];

export function StackStrip() {
  return (
    <div className="max-w-4xl mx-auto px-6 text-center">
      <p className="text-xs font-['JetBrains_Mono'] text-[var(--bs-text-muted)] uppercase tracking-widest mb-4">
        Para curiosos técnicos
      </p>
      <h2 className="font-['Space_Grotesk'] text-2xl font-bold text-[var(--bs-text-primary)] mb-4">
        Construido con tecnología abierta
      </h2>
      <p className="text-[var(--bs-text-muted)] text-sm mb-10">
        Para que puedas auditar cómo funciona.
      </p>

      <div className="flex flex-wrap justify-center gap-3 mb-8">
        {STACK_ITEMS.map((item) => (
          <div
            key={item.name}
            className="bg-[var(--bs-surface-2)] border border-[var(--bs-border)] rounded-lg px-4 py-2 text-center"
          >
            <div className="text-sm font-medium text-[var(--bs-text-primary)]">
              {item.name}
            </div>
            <div className="text-xs text-[var(--bs-text-muted)]">{item.desc}</div>
          </div>
        ))}
      </div>

      <a
        href={GITHUB_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 text-sm text-[var(--bs-text-muted)] border border-[var(--bs-border)] rounded-lg px-5 py-2.5 hover:border-[var(--bs-text-muted)] transition-colors"
      >
        <span>Ver código en GitHub</span>
        <span>→</span>
      </a>
    </div>
  );
}
```

- [ ] **Step 2: Actualizar sección 8 en `page.tsx`**

```typescript
import { StackStrip } from "@/components/marketing/StackStrip";

<section id="stack" className="py-20 bg-[var(--bs-surface-1)]">
  <StackStrip />
</section>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/marketing/StackStrip.tsx frontend/app/\(marketing\)/page.tsx
git commit -m "feat(ui): add StackStrip section for technical audience (tier-2)"
```

---

## Task 23: Sección 9 — Footer

**Archivos:**
- Create: `frontend/components/marketing/MarketingFooter.tsx`
- Modify: `frontend/app/(marketing)/page.tsx`

- [ ] **Step 1: Crear `MarketingFooter.tsx`**

```typescript
const FOOTER_LINKS = [
  { label: "Privacidad", href: "/privacy" },
  { label: "Términos", href: "/terms" },
  { label: "GitHub", href: "https://github.com/TBD/bioshield", external: true },
  { label: "press@bioshield.mx", href: "mailto:press@bioshield.mx", external: true },
];

export function MarketingFooter() {
  return (
    <footer className="border-t border-[var(--bs-border)] py-10 px-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
          <span className="font-['Pacifico'] text-[var(--bs-brand-green)] text-lg">
            BioShield
          </span>

          <nav className="flex flex-wrap justify-center gap-x-6 gap-y-2">
            {FOOTER_LINKS.map((link) => (
              <a
                key={link.label}
                href={link.href}
                target={link.external ? "_blank" : undefined}
                rel={link.external ? "noopener noreferrer" : undefined}
                className="text-xs text-[var(--bs-text-muted)] hover:text-[var(--bs-text-primary)] transition-colors"
              >
                {link.label}
              </a>
            ))}
          </nav>

          <p className="text-xs text-[var(--bs-text-muted)]">
            © 2026 BioShield AI · Hecho en MX
          </p>
        </div>

        <p className="mt-6 text-center text-xs text-[var(--bs-text-muted)]/60 max-w-xl mx-auto leading-relaxed">
          Herramienta educativa e informativa. No sustituye la consulta médica profesional.
          No avalada por COFEPRIS ni FDA. Información basada en bases de datos regulatorias públicas.
        </p>
      </div>
    </footer>
  );
}
```

- [ ] **Step 2: Actualizar footer en `page.tsx`**

```typescript
import { MarketingFooter } from "@/components/marketing/MarketingFooter";

// Reemplazar footer placeholder:
<MarketingFooter />
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/marketing/MarketingFooter.tsx frontend/app/\(marketing\)/page.tsx
git commit -m "feat(ui): add MarketingFooter with legal links and regulatory disclaimer"
```

---

## Task 24: SEO — metadata, OG image, sitemap, robots

**Archivos:**
- Modify: `frontend/app/layout.tsx`
- Create: `frontend/app/api/og/route.tsx`
- Create: `frontend/app/sitemap.ts`
- Create: `frontend/app/robots.ts`

- [ ] **Step 1: Actualizar metadata en `frontend/app/layout.tsx`**

```typescript
export const metadata: Metadata = {
  title: {
    default: "BioShield AI — Nutrición inteligente",
    template: "%s · BioShield AI",
  },
  description:
    "Escanea cualquier producto y descubre si sus aditivos son compatibles con tus análisis de laboratorio. Herramienta educativa basada en FDA, EFSA y Codex Alimentarius.",
  keywords: ["nutrición", "biomarcadores", "aditivos", "salud", "México", "EFSA", "FDA"],
  openGraph: {
    title: "BioShield AI — Nutrición inteligente",
    description: "Lo que comes, en términos de TU sangre.",
    images: [{ url: "/api/og", width: 1200, height: 630 }],
    locale: "es_MX",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "BioShield AI",
    description: "Lo que comes, en términos de TU sangre.",
    images: ["/api/og"],
  },
};
```

- [ ] **Step 2: Instalar @vercel/og si no está**

```bash
cd frontend
pnpm add @vercel/og
```

- [ ] **Step 3: Crear `frontend/app/api/og/route.tsx`**

```typescript
import { ImageResponse } from "@vercel/og";

export const runtime = "edge";

export function GET() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#0a0a0a",
          padding: "60px",
        }}
      >
        <div style={{ color: "#4ADE80", fontSize: 48, fontWeight: "bold", marginBottom: 16 }}>
          BioShield AI
        </div>
        <div style={{ color: "#ffffff", fontSize: 32, textAlign: "center", maxWidth: 700 }}>
          Lo que comes, en términos de TU sangre.
        </div>
        <div style={{ color: "#6b7280", fontSize: 18, marginTop: 24 }}>
          FDA · EFSA · Codex Alimentarius
        </div>
      </div>
    ),
    { width: 1200, height: 630 }
  );
}
```

- [ ] **Step 4: Crear `frontend/app/sitemap.ts`**

```typescript
import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = process.env.NEXT_PUBLIC_BASE_URL ?? "https://bioshield.mx";
  return [
    { url: base, lastModified: new Date(), changeFrequency: "weekly", priority: 1 },
    { url: `${base}/privacy`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.5 },
    { url: `${base}/terms`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.5 },
  ];
}
```

- [ ] **Step 5: Crear `frontend/app/robots.ts`**

```typescript
import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const base = process.env.NEXT_PUBLIC_BASE_URL ?? "https://bioshield.mx";
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/privacy", "/terms", "/api/og"],
        disallow: ["/home", "/scan", "/biosync", "/history", "/login", "/register"],
      },
    ],
    sitemap: `${base}/sitemap.xml`,
  };
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/app/layout.tsx frontend/app/api/og/route.tsx frontend/app/sitemap.ts frontend/app/robots.ts
git commit -m "feat(seo): add OG image, sitemap, robots.txt, and full metadata for landing"
```

---

## Task 25: Avatar optimization — PNGs → AVIF

**Archivos:**
- Create: `frontend/scripts/optimize-avatars.ts`

- [ ] **Step 1: Verificar tamaños actuales**

```bash
du -sh frontend/public/avatars/*.png
```

- [ ] **Step 2: Instalar sharp si no está**

```bash
cd frontend
pnpm add -D sharp
```

- [ ] **Step 3: Crear `frontend/scripts/optimize-avatars.ts`**

```typescript
import sharp from "sharp";
import { readdirSync, mkdirSync } from "fs";
import { join } from "path";

const INPUT_DIR = join(process.cwd(), "public/avatars");
const OUTPUT_DIR = join(process.cwd(), "public/avatars/avif");

mkdirSync(OUTPUT_DIR, { recursive: true });

const pngs = readdirSync(INPUT_DIR).filter((f) => f.endsWith(".png"));

for (const file of pngs) {
  const input = join(INPUT_DIR, file);
  const output = join(OUTPUT_DIR, file.replace(".png", ".avif"));

  await sharp(input)
    .resize({ width: 256, withoutEnlargement: true })
    .avif({ quality: 60, effort: 4 })
    .toFile(output);

  console.log(`✓ ${file} → avif/${file.replace(".png", ".avif")}`);
}
```

- [ ] **Step 4: Ejecutar y verificar tamaños**

```bash
cd frontend
npx tsx scripts/optimize-avatars.ts
du -sh public/avatars/avif/*.avif
```

Objetivo: cada archivo < 80KB.

- [ ] **Step 5: Commit**

```bash
git add frontend/scripts/optimize-avatars.ts frontend/public/avatars/avif/
git commit -m "perf(ui): add avatar AVIF optimization script and converted files"
```

---

## Task 26: Tests E2E Playwright — landing

**Archivos:**
- Create: `tests/specs/landing/landing.spec.ts`
- Create: `tests/specs/scan/sse-contract.spec.ts`

- [ ] **Step 1: Crear `tests/specs/landing/landing.spec.ts`**

```typescript
import { test, expect } from "@playwright/test";

test.describe("Marketing landing page", () => {
  test("/ carga sin auth y muestra el hero", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1")).toContainText("Lo que comes");
    await expect(page.locator("text=BioShield AI · Nutrición inteligente")).toBeVisible();
  });

  test("RegulatoryBanner está visible", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.locator("text=Herramienta educativa. No sustituye consulta médica")
    ).toBeVisible();
  });

  test("CTA de waitlist inline funciona", async ({ page }) => {
    await page.goto("/");
    await page.fill('input[type="email"]', "e2e@test.com");
    await page.click('button[type="submit"]');
    // Esperamos toast de éxito o de "ya estás en la lista"
    await expect(page.locator('[data-sonner-toast]')).toBeVisible({ timeout: 5000 });
  });

  test("FAQ es accesible y colapsa/expande", async ({ page }) => {
    await page.goto("/");
    await page.locator("#faq").scrollIntoViewIfNeeded();
    const firstQuestion = page.locator('[data-radix-accordion-trigger]').first();
    await firstQuestion.click();
    await expect(page.locator('[data-radix-accordion-content]').first()).toBeVisible();
  });

  test("Link 'Entrar' apunta a /login", async ({ page }) => {
    await page.goto("/");
    const link = page.locator('header a[href="/login"]');
    await expect(link).toBeVisible();
    await expect(link).toHaveText(/Entrar/);
  });

  test("Regulatory copy — sin blocklist en pantalla", async ({ page }) => {
    await page.goto("/");
    const content = await page.content();
    const blocklist = ["diagnosticamos", "diagnóstico", "riesgo cardiovascular", "predicción de"];
    for (const term of blocklist) {
      expect(content.toLowerCase()).not.toContain(term.toLowerCase());
    }
  });

  test("/home redirige a login sin sesión", async ({ page }) => {
    await page.goto("/home");
    await expect(page).toHaveURL(/\/login/);
  });
});
```

- [ ] **Step 2: Crear `tests/specs/scan/sse-contract.spec.ts`**

```typescript
import { test, expect } from "@playwright/test";
import { readFileSync, readdirSync } from "fs";
import { join } from "path";

const FIXTURES_DIR = join(process.cwd(), "frontend/public/demo");
const REQUIRED_EVENT_TYPES = ["init", "ingredients", "done"];

test.describe("SSE trace fixtures — contract test", () => {
  const fixtures = readdirSync(FIXTURES_DIR).filter((f) => f.endsWith(".json"));

  test("existen 3 fixtures generados", () => {
    expect(fixtures.length).toBeGreaterThanOrEqual(3);
  });

  for (const file of fixtures) {
    test(`fixture ${file} tiene schema correcto`, () => {
      const raw = readFileSync(join(FIXTURES_DIR, file), "utf-8");
      const trace = JSON.parse(raw);

      expect(trace).toHaveProperty("barcode");
      expect(trace).toHaveProperty("product_name");
      expect(Array.isArray(trace.events)).toBe(true);
      expect(trace.events.length).toBeGreaterThan(0);

      const types = trace.events.map((e: { type: string }) => e.type);
      for (const required of REQUIRED_EVENT_TYPES) {
        expect(types).toContain(required);
      }

      // Verificar que cada evento tiene t_ms y data
      for (const event of trace.events) {
        expect(typeof event.t_ms).toBe("number");
        expect(typeof event.type).toBe("string");
        expect(typeof event.data).toBe("object");
      }
    });
  }
});
```

- [ ] **Step 3: Correr tests**

```bash
# Asegurarse de que el dev server está corriendo en :3000
npx playwright test tests/specs/landing/ tests/specs/scan/sse-contract.spec.ts --reporter=list
```

Resultado esperado: todos verdes.

- [ ] **Step 4: Commit**

```bash
git add tests/specs/landing/ tests/specs/scan/sse-contract.spec.ts
git commit -m "test(e2e): add landing page E2E specs and SSE contract test"
```

---

## Task 27: Lighthouse CI gate

**Archivos:**
- Create: `.github/workflows/lhci.yml`

- [ ] **Step 1: Instalar @lhci/cli como devDependency**

```bash
cd frontend
pnpm add -D @lhci/cli
```

- [ ] **Step 2: Crear `lighthouserc.json` en `frontend/`**

```json
{
  "ci": {
    "collect": {
      "url": ["http://localhost:3000/"],
      "numberOfRuns": 1,
      "settings": {
        "preset": "desktop",
        "onlyCategories": ["performance", "accessibility", "best-practices", "seo"]
      }
    },
    "assert": {
      "assertions": {
        "categories:performance": ["error", { "minScore": 0.85 }],
        "categories:accessibility": ["error", { "minScore": 0.95 }],
        "categories:best-practices": ["error", { "minScore": 0.90 }],
        "categories:seo": ["error", { "minScore": 1.0 }]
      }
    },
    "upload": {
      "target": "temporary-public-storage"
    }
  }
}
```

- [ ] **Step 3: Crear `.github/workflows/lhci.yml`**

```yaml
name: Lighthouse CI

on:
  pull_request:
    paths:
      - "frontend/**"

jobs:
  lhci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: "pnpm"
          cache-dependency-path: frontend/pnpm-lock.yaml

      - name: Install frontend deps
        run: cd frontend && pnpm install --frozen-lockfile

      - name: Build
        run: cd frontend && pnpm build
        env:
          NEXT_PUBLIC_API_URL: http://localhost:8000

      - name: Start server
        run: cd frontend && pnpm start &
        env:
          PORT: 3000

      - name: Wait for server
        run: npx wait-on http://localhost:3000 --timeout 30000

      - name: Run Lighthouse CI
        run: cd frontend && npx lhci autorun --config=lighthouserc.json
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/lhci.yml frontend/lighthouserc.json
git commit -m "ci: add Lighthouse CI gate for marketing landing (P≥85, A≥95, SEO=100)"
```

---

## Task 28: PR y verificación final pre-merge

- [ ] **Step 1: Regulatory copy grep — cero ocurrencias del blocklist**

```bash
grep -rni "detectamos\|riesgo cardiovascular\|diagnóstico\|biomarker matching\|analizamos tu salud\|predicción de\|previene\|cura\|tratamiento" \
  frontend/app/\(marketing\)/ frontend/components/marketing/ | grep -v ".git"
```

Resultado esperado: sin output (cero ocurrencias).

- [ ] **Step 2: Verificar TTFB de `/` sin JWT**

```bash
for i in {1..5}; do
  curl -s -o /dev/null -w "%{time_total}s\n" http://localhost:3000/
done
```

Resultado esperado: consistentemente < 0.2s.

- [ ] **Step 3: Verificar viewport 375px (mobile) y 1440px (desktop)**

Abrir DevTools → Device toolbar y verificar que no hay overflow horizontal en ninguna sección.

- [ ] **Step 4: Correr suite completa de tests**

```bash
# Backend
cd backend && pytest tests/ -v

# Frontend type check
cd frontend && pnpm tsc --noEmit

# E2E
npx playwright test tests/specs/landing/ tests/specs/scan/ --reporter=list
```

Resultado esperado: todos verdes.

- [ ] **Step 5: Push y PR**

```bash
git push -u origin feature/marketing-landing
gh pr create \
  --title "feat(marketing): landing page with waitlist, pipeline demo, and regulatory compliance" \
  --body "$(cat <<'EOF'
## Summary
- Landing pública en `/` con 9 secciones (hero, reveal, how, why, trust, waitlist, FAQ, stack, footer)
- Backend waitlist: POST /waitlist + GET /count con idempotencia LFPDPPP, Turnstile, consent_text
- Dashboard movido de `/` a `/home` con middleware restrictivo (TTFB sin JWT decode)
- Demo pipeline replica SSE trace real desde fixtures JSON generados
- RegulatoryBanner + DemoDisclaimerModal para compliance FTC/COFEPRIS
- Lighthouse CI gate: P≥85, A≥95, SEO=100

## Test plan
- [ ] `pytest tests/test_waitlist.py -v` — 6 tests verdes
- [ ] `playwright test tests/specs/landing/` — 6 tests verdes
- [ ] `playwright test tests/specs/scan/sse-contract.spec.ts` — fixtures válidos
- [ ] Regulatory grep: cero ocurrencias del blocklist
- [ ] Manual: flujo waitlist (submit → 201 → toast OK; duplicado → 409)
- [ ] Manual: `/home` sin auth → redirige a `/login`
- [ ] Manual: `/` accesible sin auth → landing visible

## Pre-launch gates pendientes (fuera de este PR)
- [ ] Fixtures SSE generados con backend real (record_demo_trace.py)
- [ ] Cloudflare Turnstile keys en env de producción
- [ ] N_INGREDIENTS actualizado con SELECT COUNT(*) real
- [ ] Canales de distribución con owner+CAC+deadline asignados
EOF
)"
```

---

## Resumen de archivos creados/modificados

### Backend (5 archivos nuevos, 2 modificados)
| Archivo | Acción |
|---|---|
| `backend/app/models/__init__.py` | +WaitlistSignup model |
| `backend/alembic/versions/{rev}_add_waitlist_signups.py` | Nuevo |
| `backend/app/routers/waitlist.py` | Nuevo |
| `backend/app/config.py` | +turnstile_secret_key |
| `backend/app/main.py` | +include_router(waitlist) |
| `backend/scripts/record_demo_trace.py` | Nuevo |
| `backend/scripts/expire_waitlist.py` | Nuevo |
| `backend/tests/test_waitlist.py` | Nuevo |

### Frontend — routing (7 archivos)
| Archivo | Acción |
|---|---|
| `frontend/app/(app)/home/page.tsx` | Nuevo (movido de `/page.tsx`) |
| `frontend/app/(app)/page.tsx` | Eliminado |
| `frontend/middleware.ts` | Nuevo |
| `frontend/app/(app)/layout.tsx` | `href="/"` → `/home` |
| `frontend/app/(auth)/login/page.tsx` | `router.push("/")` → `/home` |
| `frontend/app/(auth)/register/page.tsx` | `router.push("/")` → `/home` |
| `frontend/app/(app)/biosync/page.tsx` | 2 cambios |
| `frontend/components/BottomNav.tsx` | Item Home → `/home` |

### Frontend — marketing (15 componentes nuevos)
Todos en `frontend/components/marketing/` y `frontend/app/(marketing)/`.

### SEO + CI (4 archivos nuevos)
`frontend/app/api/og/route.tsx`, `frontend/app/sitemap.ts`, `frontend/app/robots.ts`, `.github/workflows/lhci.yml`

### Tests (2 archivos nuevos)
`tests/specs/landing/landing.spec.ts`, `tests/specs/scan/sse-contract.spec.ts`
