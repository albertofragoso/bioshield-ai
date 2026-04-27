# Fase 7 — Frontend BioShield AI: Implementación Next.js con design system propio

## Context

El backend MVP está **cerrado y verde** (90 tests passing, 11 endpoints expuestos, pipeline LangGraph funcional con semáforo 5 colores, OCR Gemini Vision validado con 13 etiquetas MX reales). El bloqueante principal del proyecto — documentado en `docs/reviews/18-04.md §5` (red flag #5) — es la **ausencia de UI**: sin frontend no hay dogfood end-to-end, no se puede entrevistar usuarios, y el PRD Fase 2 (Retail Integration) y Fase 3 (Reality Engineering) quedan bloqueados por falta de signal de uso real.

El design system (dark-only, 12 avatares mascota, Pacifico + Space Grotesk + JetBrains Mono) ya está materializado en `frontend/app/globals.css` y documentado en `docs/design/tokens.md`. Login y Register ya están implementados con ese system; el login además entregó un paquete handoff completo en `docs/design/login/` (README + `design-tokens.json` + HTML prototype) que queda como referencia histórica. Las 6 pantallas pendientes (Scanner, Resultado, Biosync, Dashboard real, Historial, Polish global) se implementan **directo en Next.js** a partir de las specs embebidas en este plan, sin pasar por una plataforma de diseño intermedia.

Fase 7 cubre 6 items (7.1-7.6) del review. Este plan los descompone en:
1. **Setup monorepo `/frontend`** (Next.js 15 + Tailwind + shadcn/ui + TanStack Query + Zustand). ✅
2. **Design system tokens** (semáforo, typography, look biotech confiable). ✅
3. **6 pantallas pendientes con spec embebida** (data shape, estados, componentes, tokens, avatar, tono). Claude Code las implementa directamente; Alberto valida en `pnpm dev`.
4. **Componentes compartidos on-demand** — semáforo / ingredients / scanner / biosync nacen inline en la primera pantalla y se extraen a `components/` cuando aparezca un segundo consumer.
5. **Verificación end-to-end** — scan de barcode + photo + biosync upload, desde UI hasta pipeline.

**Outcome esperado:** MVP demostrable a terceros, base para calibración HITL (§2.2 del review) y para entrevistas de usuarios (red flag #4).

---

## Fase A — Setup del monorepo `/frontend`

### Estructura objetivo

```
bio_shield/
├── backend/              (existente)
├── frontend/             (NUEVO)
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   ├── (app)/
│   │   │   ├── layout.tsx           # navbar + guard JWT
│   │   │   ├── page.tsx             # Dashboard
│   │   │   ├── scan/page.tsx        # Scanner
│   │   │   ├── scan/[id]/page.tsx   # Resultado
│   │   │   ├── history/page.tsx     # ScanHistory list
│   │   │   └── biosync/page.tsx     # Biosync upload/status
│   │   ├── api/                     # proxy routes si hace falta (cookies SSR)
│   │   ├── globals.css
│   │   └── layout.tsx
│   ├── components/
│   │   ├── ui/                      # shadcn/ui (generados por CLI)
│   │   ├── semaphore/               # SemaphoreBadge, SemaphoreCard
│   │   ├── scanner/                 # BarcodeScanner, PhotoCapture
│   │   ├── ingredients/             # IngredientList, ConflictDetail
│   │   └── biosync/                 # BiomarkerForm, BiomarkerCSVUpload
│   ├── lib/
│   │   ├── api/                     # fetcher tipado + tipos generados
│   │   │   ├── client.ts            # fetch con credentials:"include" + refresh
│   │   │   ├── auth.ts              # login/register/logout/refresh
│   │   │   ├── scan.ts              # barcode/photo
│   │   │   ├── biosync.ts           # upload/status/delete
│   │   │   └── types.ts             # mirror de backend/app/schemas/models.py
│   │   ├── stores/
│   │   │   └── auth.ts              # Zustand: user, isAuthenticated
│   │   └── utils.ts
│   ├── tests/
│   │   └── e2e/                     # Playwright (opcional fase A.4)
│   ├── .env.local.example           # NEXT_PUBLIC_API_URL
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── components.json              # shadcn config
│   ├── package.json
│   └── CLAUDE.md                    # Contexto FE para Claude Code
├── docs/
│   └── design/                      # NUEVO — screenshots + specs por pantalla
└── docker-compose.yml               # extender con servicio `frontend`
```

### A.1 · Bootstrap

```bash
# desde raíz del repo
pnpm dlx create-next-app@latest frontend \
  --typescript --tailwind --eslint --app --src-dir=false \
  --import-alias="@/*" --use-pnpm
cd frontend
pnpm dlx shadcn@latest init           # style: default, color: slate (sobrescribiremos)
pnpm add @tanstack/react-query zustand zod
pnpm add -D @tanstack/react-query-devtools
pnpm dlx shadcn@latest add button card input label toast dialog sheet \
  form alert badge progress skeleton tabs separator avatar
```

Para scanner (item 7.3): `pnpm add @zxing/browser @zxing/library` (preferido sobre `react-qr-barcode-scanner` porque tiene mantenimiento activo y menos deps).

### A.0 · `frontend/CLAUDE.md` — crear junto con el bootstrap

Crear `frontend/CLAUDE.md` inmediatamente después del bootstrap, siguiendo el mismo patrón que `backend/CLAUDE.md` (sección "Qué es" → "Stack" con referencia al root CLAUDE.md → "Convenciones" específicas → "Estructura" → "Docs de referencia" → "Cómo correr" → "Variables de entorno").

Contenido exacto a crear:

```markdown
# BioShield AI — Frontend

## Qué es

Frontend Next.js 15 (App Router) que consume la API REST del backend FastAPI.
Permite al usuario escanear productos (cámara barcode + foto etiqueta), visualizar
el semáforo nutricional con detalle de conflictos por ingrediente, y gestionar sus
biomarcadores de sangre para alertas personalizadas.

## Stack

> Stack completo y convenciones de negocio en `.claude/CLAUDE.md` (raíz del repo).

Adiciones específicas del frontend:

- **Framework:** Next.js 15 con App Router y TypeScript strict
- **Estilos:** Tailwind CSS v4 + shadcn/ui (Radix primitives)
- **Server state:** TanStack Query v5 (cache, mutations, retry)
- **Client state:** Zustand (auth: user, isAuthenticated)
- **Validación:** Zod (schemas que espejean `backend/app/schemas/models.py`)
- **Scanner barcode:** @zxing/browser + @zxing/library
- **Auth:** JWT via HTTP-only cookies — el frontend NUNCA lee los tokens directamente

## Convenciones

- **Cliente API:** todo fetch pasa por `lib/api/client.ts`. Nunca llamar `fetch()` directo en componentes.
- **Tipos:** `lib/api/types.ts` es el espejo de los schemas del backend. Si el backend cambia un schema, actualizar aquí también. En CI se valida paridad con `openapi-typescript`.
- **Cookies:** el backend setea las cookies; Next.js las envía automáticamente con `credentials: "include"`. No usar `localStorage` para tokens.
- **Refresh automático:** `client.ts` intercepta 401, llama `POST /auth/refresh`, reintenta la request original. Si refresh falla, redirige a `/login`.
- **Semáforo:** los 5 colores (GRAY/BLUE/YELLOW/ORANGE/RED) nunca se usan como único indicador — siempre acompañados de icono + label textual (WCAG AA).
- **Variables de entorno:** solo `NEXT_PUBLIC_API_URL` es pública. No exponer secretos en variables `NEXT_PUBLIC_*`.
- **Componentes shadcn/ui:** generar con `pnpm dlx shadcn@latest add <componente>`. No modificar `components/ui/` manualmente.
- **Server Components vs Client Components:** preferir Server Components; usar `"use client"` solo donde haya interactividad (scanner, formularios, stores).

## Estructura

```
frontend/
├── app/
│   ├── (auth)/                      # Rutas públicas (sin guard JWT)
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   ├── (app)/                       # Rutas protegidas
│   │   ├── layout.tsx               # Navbar + guard JWT (redirect a /login si 401)
│   │   ├── page.tsx                 # Dashboard
│   │   ├── scan/page.tsx            # Scanner (barcode + photo tabs)
│   │   ├── scan/[id]/page.tsx       # Resultado del scan (semáforo + ingredientes)
│   │   ├── history/page.tsx         # Historial de scans
│   │   └── biosync/page.tsx         # Upload/status de biomarcadores
│   ├── globals.css                  # CSS vars de semáforo + tokens de marca
│   └── layout.tsx                   # QueryClientProvider + ThemeProvider
├── components/
│   ├── ui/                          # shadcn/ui — NO editar manualmente
│   ├── semaphore/                   # SemaphoreHero, SemaphoreBadge
│   ├── scanner/                     # BarcodeScanner, PhotoCapture
│   ├── ingredients/                 # IngredientCard, ConflictDetail
│   └── biosync/                     # BiomarkerForm, BiomarkerCSVUpload
├── lib/
│   ├── api/
│   │   ├── client.ts                # fetch wrapper con credentials + retry en 401
│   │   ├── auth.ts                  # login / register / logout / refresh
│   │   ├── scan.ts                  # scanBarcode / scanPhoto
│   │   ├── biosync.ts               # uploadBiomarkers / getStatus / deleteBiomarkers
│   │   └── types.ts                 # Espejo de backend/app/schemas/models.py
│   ├── stores/
│   │   └── auth.ts                  # Zustand: user, setUser, logout
│   └── utils.ts
├── .env.local.example
├── next.config.ts
├── tailwind.config.ts
├── components.json                  # shadcn config
└── CLAUDE.md                        # Este archivo
```

## Documentación de referencia

- **Plan Fase 7 (este sprint):** `.claude/plans/unified-sniffing-feather.md`
- **Arquitectura general:** `docs/architecture.md`
- **Specs de implementación por pantalla:** `.claude/plans/frontend.md` → Fase C
- **Handoff histórico del login (referencia visual):** `docs/design/login/README.md`
- **Schemas del backend (source of truth de tipos):** `backend/app/schemas/models.py`
- **Reglas de biomarcadores (hints del form Biosync):** `backend/app/services/analysis.py`
- **Next.js 15 App Router:** https://nextjs.org/docs/app
- **shadcn/ui:** https://ui.shadcn.com
- **TanStack Query v5:** https://tanstack.com/query/v5
- **@zxing/browser:** https://github.com/zxing-js/library

## Cómo correr el frontend

```bash
# Primera vez
cd frontend
pnpm install

# Desarrollo (hot-reload, apunta a backend en :8000)
cp .env.local.example .env.local   # ajustar NEXT_PUBLIC_API_URL si es necesario
pnpm dev                            # http://localhost:3000

# Build de producción
pnpm build
pnpm start

# Stack completo con Docker (backend + frontend + postgres)
# desde raíz del repo:
docker compose up --build
```

## Variables de entorno

| Variable | Descripción | Default dev |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | URL base del backend FastAPI | `http://localhost:8000` |

Ver `.env.local.example` para referencia completa.
```

### A.2 · Cliente API tipado

`frontend/lib/api/client.ts` — wrapper de `fetch` con:
- `credentials: "include"` (cookies HTTP-only del backend).
- Retry automático en 401: llama `POST /auth/refresh`, si ok reintenta la request original; si falla, redirige a `/login`.
- Base URL desde `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
- Parseo Zod en cada response para catch temprano de drift entre FE/BE.

`frontend/lib/api/types.ts` — replica exacta de `backend/app/schemas/models.py`. Espejo manual ahora; más adelante generar con `openapi-typescript` contra `/openapi.json` (incluir en CI como check de paridad).

### A.3 · CORS backend

Verificar `backend/.env` → `ALLOWED_ORIGINS=["http://localhost:3000"]` (ya está). Para prod, agregar dominio de deploy (Vercel/Render).

### A.4 · docker-compose extensión

Agregar servicio `frontend`:
```yaml
frontend:
  build: ./frontend
  environment:
    NEXT_PUBLIC_API_URL: http://backend:8000
  ports: ["3000:3000"]
  depends_on: [backend]
```

---

## Fase B — Design system tokens ✅ IMPLEMENTADO

Materializados en `frontend/app/globals.css` (Tailwind v4 `@theme` + `:root` dark-only).
Documentación canónica: `docs/design/tokens.md`.

### Decisiones tomadas (2026-04-21)

| Dimensión | Decisión final |
|---|---|
| Paleta primary | `#4ADE80` (green) — derivado del avatar mascota, adoptado del login |
| Modo | **Dark-only** — `<html class="dark">` forzado, sin variante light |
| Fuentes | Pacifico (wordmark) + Space Grotesk (cuerpo) + JetBrains Mono (labels/meta) |
| Inter | **Retirada** del stack |
| Efectos | Hex-grid SVG + scanlines + glows en **todas** las pantallas (via `body` global) |
| Avatares PNG | Adicionales al lado del semáforo (nunca solos — WCAG AA) |

### B.1 · Paleta — Marca + semáforo

**Marca** (derivada del avatar mascota piña/escudo ADN):

| Token CSS | HEX | Tailwind | Uso |
|---|---|---|---|
| `--brand-green` | `#4ADE80` | `bg-brand-green` / `text-brand-green` | Primary — CTA, bordes activos, glows |
| `--brand-amber` | `#F59E0B` | `bg-brand-amber` | Accent — wordmark "AI", banners expiración |
| `--brand-teal` | `#2DD4BF` | `bg-brand-teal` | Secondary — links olvidé contraseña |
| `--brand-red` | `#F87171` | `bg-brand-red` | Error — alert 401 |
| `--brand-amber-warn` | `#FCD34D` | `bg-brand-amber-warn` | Warning — alert 429 |
| `--background` | `#080C07` | `bg-background` | Fondo global (hex-grid + scanlines en `body`) |
| `--surface` / `--card` | `#0D1310` | `bg-surface` / `bg-card` | Cards, popovers, inputs |
| `--foreground` | `#DCF0DC` | `text-foreground` | Texto principal |
| `--subtext` | `#6B8A6A` | `text-subtext` | Labels, placeholders, metadata |
| `--border` | `rgba(74,222,128,0.18)` | `border-border` | Bordes card/input idle |

**Semáforo ajustado para dark** (ratios WCAG AA verificados contra `#080C07`):

| Estado | Token | HEX | Ratio | Icono Lucide | Label |
|---|---|---|---|---|---|
| GRAY | `--semaphore-gray` | `#A8B3A7` | 9.1:1 | `HelpCircle` | "Sin datos suficientes" |
| BLUE | `--semaphore-blue` | `#60A5FA` | 7.2:1 | `CheckCircle` | "Seguro" |
| YELLOW | `--semaphore-yellow` | `#FACC15` | 13.4:1 | `AlertCircle` | "Precaución" |
| ORANGE | `--semaphore-orange` | `#FB923C` | 9.0:1 | `AlertTriangle` | "Riesgo personal" |
| RED | `--semaphore-red` | `#F87171` | 6.8:1 | `ShieldAlert` | "Prohibido" |

### B.2 · Typography

Cargadas en `app/layout.tsx` con `next/font/google`:

| Familia | Variable | Tailwind | Pesos | Uso |
|---|---|---|---|---|
| Pacifico | `--font-pacifico` | `font-display` | 400 | Solo wordmark "BioShield" |
| Space Grotesk | `--font-space-grotesk` | `font-sans` | 300–700 | Cuerpo: inputs, botones, párrafos |
| JetBrains Mono | `--font-jetbrains-mono` | `font-mono` | 400–700 | Labels UPPERCASE, alerts `[ERROR_XXX]`, CAS, E-numbers, barcodes |

Escala: `text-[9px]` metadata · `text-[10px]` labels · `text-xs 12` · `text-sm 14` · `text-base 16` · `text-lg 18` · `text-xl 20` · `text-2xl 24` · `text-4xl 36` (hero).

### B.3 · Espaciado & radius

| Token | Valor | Tailwind | Uso |
|---|---|---|---|
| `--radius-card` | 18px | `rounded-card` | Card principal |
| `--radius-input` | 8px | `rounded-input` | Inputs, alerts |
| `--radius-button` | 10px | `rounded-button` | Botones |
| Card padding desktop | `40px 36px 36px` | — | Padding del card auth |
| Card padding mobile | `28px 16px 24px` | — | En 375px |

### B.4 · Iconografía

**Lucide React** (ya viene con shadcn). Iconos clave: `Camera`, `Barcode`, `Activity` (biomarcadores), `ShieldCheck` (brand), `AlertTriangle`, `CheckCircle`, `HelpCircle`, `AlertCircle`, `ShieldAlert`, `History`, `WifiOff`.

### B.5 · Motion

Keyframes disponibles en `globals.css`:

| Clase | Keyframes | Duración | Uso |
|---|---|---|---|
| `animate-wobble` | translateY + rotate 6-step | 5s infinite | Avatar mascota idle |
| `animate-scan-line` | translateY -100%→100% | 2s linear infinite | Línea láser barcode |
| `animate-pulse-glow` | opacity + drop-shadow | 2.4s infinite | Avatar semáforo en resultado |
| `animate-pulse` (Tailwind) | opacity 1↔0.5 | 2s infinite | Semáforo al cambiar color |

Transición estándar: `0.2s ease`. `transform-origin: bottom center` en avatar wobble.

### B.6 · Efectos visuales globales (en body — todas las pantallas)

1. **Hex-grid:** SVG 56×64px con trazo `rgba(74,222,128,0.04)`
2. **Glow radial superior:** verde sutil en `50% 0%`
3. **Glow radial inferior derecho:** ámbar sutil en `80% 90%`
4. **Scanlines:** `body::after` con `repeating-linear-gradient` cada 4px, `pointer-events: none`

No requieren wrappers extra en componentes — ya aplicados en `globals.css`.

Utilidades adicionales: `bs-card` (card + glow), `bs-corner-{tl,tr,bl,br}` (corner accents), `bs-glow-green`, `bs-glow-green-strong`, `bs-input-focus`, `bs-mascot-glow`.

### B.7 · Avatares mascota (`/public/avatars/`)

12 PNG disponibles con fondo alpha transparente (992×1063px → renderizar a tamaño objetivo):

| Archivo | Contexto | Tamaño |
|---|---|---|
| `main.png` | Login, Register — hero con `animate-wobble` + `bs-mascot-glow` | 140×140 |
| `welcome.png` | Dashboard primer login, empty state onboarding | 120×120 |
| `progress.png` | Loading de `/scan` procesando foto | 100×100 |
| `success.png` | Toast/confirmación biosync upload OK | 80×80 |
| `profile.png` | Avatar usuario en header autenticado | 40×40 |
| `support.png` | Empty state errores, fallback 500 | 120×120 |
| `share.png` | Reservado — feature "compartir scan" | — |
| `gray/blue/yellow/orange/red.png` | Lado del badge semáforo en `/scan/[id]` | 120×120 |

**Regla:** avatares de semáforo van **al lado** de badge color + icono Lucide + label textual. Nunca solos. `alt=""` + `aria-hidden` porque la info semántica ya la entregan icono + label.

### B.8 · Accesibilidad

- WCAG AA mínimo — todos los semáforos verificados (ratios en B.1).
- Semáforo: siempre **color + icono Lucide + label textual** (+ avatar PNG decorativo).
- Focus visible en todo interactivo (shadcn ya lo trae).
- `aria-live="polite"` en hero del semáforo para screen readers.

---

## Fase C — Specs de implementación por pantalla

Claude Code lee cada spec y la implementa directamente en Next.js, reusando `AuthField`, `AuthAlert`, los tokens de `globals.css`, los avatares PNG de `/public/avatars/` y los componentes shadcn/ui ya generados. Alberto valida visual en `pnpm dev` antes de cerrar cada pantalla. Orden: Scanner + Resultado → Biosync → Dashboard real → Historial → Polish global.

Cada spec sigue la misma estructura: **data shape → estados → componentes → tokens → avatar → responsive → tono**.

---

### Pantalla 1 — Login (`/login`) ✅ IMPLEMENTADA

Handoff completo preservado en `docs/design/login/` (README + `design-tokens.json` + `reference/BioShield Login.html`). Queda como **referencia histórica** del formato original — las pantallas nuevas NO replican ese paquete (plan + código son source of truth).

---

### Pantalla 2 — Register (`/register`) ✅ IMPLEMENTADA

Código en `app/(auth)/register/page.tsx`. `PasswordStrengthBar` vive inline (verde/ámbar/rojo según longitud + variedad) — extraer a `components/auth/` solo si reusamos fuerza de password en otra pantalla.

Checkpoints de la spec original (preservados como referencia):
- `POST /auth/register` → `{ email, password: min 8 chars }` → response 201 `UserResponse` → auto-login con `POST /auth/login`.
- Errores: 409 "Email ya registrado", validación inline password < 8 chars, red.
- Misma estética que Login: card + corner accents + avatar mascota con wobble (`main.png`).
- Checkbox "acepto términos y política de datos médicos" obligatorio.
- Párrafo de privacidad LOAD-BEARING con `ShieldCheck` verde: "Tus biomarcadores se encriptan con AES-256 y se borran automáticamente después de 180 días. Nunca los compartimos."
- Post-register: `router.push('/')` (dashboard, no `/dashboard`).

---

### Pantalla 3 — Dashboard / Home (`/`)

ROUTE: `/` (autenticado — dentro del grupo `(app)/`)
PROPÓSITO: landing post-login. Tres acciones visibles: escanear producto, subir biomarcadores, ver historial.

DATA SHAPE consumida:
- GET /biosync/status →
  { id: uuid, uploaded_at, expires_at, has_data: bool }
  o 404 si no tiene biomarkers.
- GET /scan/history (endpoint futuro — para este mockup asume array de
  { id, product_name, semaphore: "GRAY"|"BLUE"|"YELLOW"|"ORANGE"|"RED",
    scanned_at }, últimos 5).

COMPONENTES:
- Header con logo + nombre de usuario + avatar + menú dropdown (logout).
- Hero card con CTA grande "Escanear producto" (icono Camera/Barcode).
- Secondary card "Subir biomarcadores" (icono Activity):
  - Si has_data=true: muestra "Biomarcadores activos · expira en X días"
    con badge ámbar si <30 días.
  - Si no tiene: muestra "Sube tu panel de sangre para alertas
    personalizadas" + botón "Subir".
- Card "Historial reciente": lista de 5 últimos scans con:
  - Thumbnail pequeño del semáforo (círculo color + icono).
  - Nombre del producto + fecha relativa ("hace 2h").
  - Chevron para ver detalle.
- Link "Ver todo el historial" al final.

ESTADOS:
- Loading: skeletons en cada card.
- Empty (sin scans): ilustración amigable + mensaje "Escanea tu primer
  producto para empezar".
- Error GET: toast + fallback "No pudimos cargar tu historial."

SEMÁFORO — CONVENCIONES VISUALES (USAR EN TODAS LAS PANTALLAS):
Colores ajustados para dark (WCAG AA verificado contra #080C07):
- GRAY   (#A8B3A7)  → icono HelpCircle   → "Sin datos suficientes"
- BLUE   (#60A5FA)  → icono CheckCircle  → "Seguro"
- YELLOW (#FACC15)  → icono AlertCircle  → "Precaución"
- ORANGE (#FB923C)  → icono AlertTriangle → "Riesgo personal"
- RED    (#F87171)  → icono ShieldAlert  → "Prohibido"
Nunca uses solo el color — siempre icono + label + (opcional) avatar PNG.

AVATAR PARA ESTADOS VACÍOS:
- Sin scans: usar welcome.png (120×120) en empty state del historial reciente.
- Header de usuario autenticado: profile.png (40×40, rounded-full).

TOKENS (dark-only):
- Background global: #080C07 con hex-grid + scanlines (heredados del body).
- Cards: background #0D1310, border rgba(74,222,128,0.18), borde-radius 18px.
- Primary: #4ADE80 — CTA principal, bordes activos.
- Amber: #F59E0B — banners de biomarcadores expirando, badges de alerta.
- Font sans: Space Grotesk. Font mono: JetBrains Mono (labels, metadata).
- CTA principal: bs-card + bs-glow-green. Hover: bs-glow-green-strong.

RESPONSIVE:
- Mobile-first. En mobile: cards apiladas, CTA principal full-width.
- Desktop ≥768px: grid 2 columnas (CTA + biosync arriba, historial full-width abajo).

TONO: biotech confiable. Acogedor al primer uso, denso en info para recurrentes.
La estética oscura con glows verdes no debe sentirse intimidante — el tono
de copy es claro y humano, la UI es lo que es sci-fi.

---

### Pantalla 4 — Scanner (`/scan`)

ROUTE: `/scan`

DOS MODOS EN LA MISMA PANTALLA (con Tabs):
  TAB 1: "Código de barras" (cámara con overlay de guía rectangular).
  TAB 2: "Foto de etiqueta" (captura frontal/trasera de la cámara o upload).

DATA FLOW:
- Barcode mode:
  - Librería: @zxing/browser lee código.
  - Al detectar: POST /scan/barcode { barcode: "8-14 dígitos" }
  - Response: ScanResponse (ver Pantalla 5 para shape) o 404 si no se encontró
    en Open Food Facts → fallback "Intenta con /scan/photo".
- Photo mode:
  - Input file o captura de cámara.
  - Valida <10 MB.
  - Convierte a base64.
  - POST /scan/photo { image_base64: string }
  - Response: ScanResponse.
  - [FASE 2] Si el usuario activa el toggle "Contribuir a Open Food Facts" (off por defecto):
    * Tras recibir ScanResponse exitoso (source="photo"), hacer:
      POST /scan/contribute {
        barcode: ScanResponse.product_barcode,
        ingredients: ScanResponse.ingredients.map(i => i.name),
        image_base64: <el mismo base64 del scan>,
        consent: true,
        scan_history_id: ScanResponse.id (si aplica)
      }
    * Response 202: toast success "Gracias por contribuir a Open Food Facts".
    * Error 4xx/5xx: toast warning no bloqueante; el scan result sigue visible.

ESTADOS:
- Barcode tab:
  - Permiso cámara pendiente → card "Permitir cámara" con botón.
  - Permiso denegado → fallback a input manual "Ingresar barcode".
  - Escaneando → overlay con animación de línea láser horizontal.
  - Detectado → flash verde breve antes de navegar al resultado.
  - Not found 404 → modal "No encontramos este producto.
    ¿Quieres intentar con foto?" + CTA que cambia al tab 2.
- Photo tab:
  - Upload idle: dropzone con "Arrastra o selecciona foto de la etiqueta".
  - Procesando: skeleton con mensaje "Analizando etiqueta con IA (5-8s)".
  - Error 413: alerta "Imagen muy grande (máx 10MB)".
  - Error 422: "No pudimos leer la etiqueta. Intenta con mejor luz."
  - [FASE 2] Toggle "Contribuir a OFF" debajo del dropzone (off por defecto, mandato PRD §9.6):
    * Label: "Contribuir esta foto a Open Food Facts (ODbL)".
    * Sub-label (text-xs, #6B8A6A): "Ayuda a que otros usuarios encuentren este producto.
      Solo enviamos ingredientes + imagen, sin datos personales."
    * Link "¿Qué significa ODbL?" → tooltip con explicación corta + link a /privacy#off.
    * Visible solo en Photo tab (no en Barcode tab si el barcode se encontró en OFF).

COMPONENTES:
- Header con botón back a Dashboard.
- Tabs horizontales (shadcn Tabs).
- Contenido tab 1: video preview 4:3 + overlay + input manual debajo "O ingresar código".
- Contenido tab 2: dropzone drag-and-drop + botón "Tomar foto" (mobile).
- [FASE 2] OFFContributeToggle: shadcn Switch + Label + sub-label + Tooltip (Info icon Lucide 12px).
  Layout: borde rgba(74,222,128,.2) sutil, padding 12px, rounded-md. Solo visible en photo tab.
- Loading global: overlay con spinner + texto explicativo.

AVATAR SCANNER:
- Al procesar foto (loading de 5-8s): progress.png (100×100) con animate-pulse-glow
  en lugar del spinner genérico. Texto "Analizando etiqueta con IA..." debajo.
- Permiso denegado / fallback: support.png (80×80) con mensaje empático.

TOKENS (dark-only):
- Background: #080C07 con hex-grid + scanlines heredados.
- Overlay del visor barcode: rgba(0,0,0,0.5) con borde verde #4ADE80.
- Línea láser del scanner: verde #4ADE80, animate-scan-line (keyframe en globals.css).
- Flash de detección: fondo verde rgba(74,222,128,0.15) en el visor, 300ms.
- Tabs: shadcn Tabs, borde activo #4ADE80, texto inactivo #6B8A6A.
- Dropzone: border dashed rgba(74,222,128,0.3), hover border rgba(74,222,128,0.6).
- [FASE 2] Toggle OFF: bg cuando off #1A2416, bg cuando on #4ADE80, thumb #E8F5E8.
- Botones: bs-card + bs-glow-green.
- Font mono: JetBrains Mono para textos de estado y labels.

RESPONSIVE:
- Mobile: video full-width, controles grandes (botones 44px mín).
- Desktop: video max-width 640px centrado.

TONO: instructivo pero no paternalista. Mensajes cortos. Errores con
opción de recuperación, nunca callejón sin salida.

---

### Pantalla 5 — Resultado de Scan (`/scan/[id]`)

**Esta es LA pantalla crítica del producto.** Spec más densa del plan.

ROUTE: `/scan/[id]`

DATA SHAPE (ScanResponse del backend):
{
  product_barcode: string,
  product_name: string | null,
  semaphore: "GRAY" | "BLUE" | "YELLOW" | "ORANGE" | "RED",
  conflict_severity: "HIGH" | "MEDIUM" | "LOW" | null,
  source: "barcode" | "photo",
  scanned_at: ISO timestamp,
  ingredients: [
    {
      name: string,                  // "Sucralose"
      canonical_name: string | null, // "Sucralose"
      cas_number: string | null,     // "56038-13-2"
      e_number: string | null,       // "E955"
      regulatory_status: "Approved" | "Banned" | "Restricted" | "Under Review" | null,
      confidence_score: float,       // 0.0-1.0
      conflicts: [
        {
          conflict_type: "REGULATORY" | "SCIENTIFIC" | "TEMPORAL",
          severity: "HIGH" | "MEDIUM" | "LOW",
          summary: string,           // "Banned in EFSA since 2018 due to..."
          sources: ["FDA", "EFSA", "Codex"]
        }
      ]
    }
  ]
}

LAYOUT (top-to-bottom):

1. HERO DEL SEMÁFORO (above-the-fold):
   - Círculo grande 120px con color del semáforo + icono al centro.
   - Pulse animation sutil.
   - Título H1 con label: "Seguro" / "Precaución" / "Riesgo personal" /
     "Prohibido" / "Sin datos suficientes".
   - Subtítulo con product_name o "Producto sin nombre" + barcode en mono.
   - Badge de severity si aplica ("HIGH severity", colores matching).

2. EXPLICACIÓN CONTEXTUAL (1-2 líneas):
   - BLUE: "Todos los ingredientes están aprobados y no encontramos conflictos."
   - YELLOW: "Detectamos X ingredientes con restricciones o conflictos entre agencias."
   - ORANGE: "Este producto contiene ingredientes que pueden afectar tu
     perfil de biomarcadores (LDL alto / glucosa alta / ...)."
   - RED: "Contiene X ingredientes prohibidos en al menos una jurisdicción."
   - GRAY: "No pudimos resolver suficientes ingredientes con confianza."

3. SECCIÓN "PARA TI" — fila dedicada (full-width, debajo del grid hero+ingredientes):
   - Renderizar solo si `data.personalized_insights.length > 0`.
   - Layout: Row 1 = grid `[300px hero | 1fr ingredientes]`; Row 2 = Para Ti ancho completo.
   - Header horizontal: H2 "Para ti" a la izquierda, tabs Alertas/Vigilar fijos 256px a la derecha (`sm:flex-row`).
   - Carousel scroll-snap (`overflow-x-auto snap-x snap-mandatory`), cards `w-full sm:w-[460px]`.
     - Swipe nativo en mobile; scroll programático en desktop vía `trackRef.current.scrollTo`.
     - Dots de navegación: pill activo 16px, círculo inactivo 6px.
     - Cambio de tab resetea al primer card y hace scroll a `left: 0`.
   - `kind === "alert"` → tab Alertas; `kind === "watch"` → tab Vigilar.
   - `DiagnosticInsightCard` por insight:
     - Row 0: `<AvatarGlow>` 56px + `friendly_biomarker_label` + `StatusPill` (ALTO/BAJO/NORMAL).
     - Row 1: valor numérico grande (30px mono) + unidad.
     - Row 2: `BiomarkerRangeBar` — track animado con zonas low/normal/high + marker dot con halo y ring; usa `reference_range_low`/`reference_range_high`.
     - Row 3: "Este producto lo movería ↑↑" — `ImpactArrows` según `impact_direction` y `severity`.
     - Row 4: `friendly_explanation` + `friendly_recommendation`.
     - Row 5: chips de `affecting_ingredients`.
   - Separador visual sutil `border-top rgba(green, .08)` entre Row 1 y Row 2 del layout.
   - `BiomarkerClearState`: card full-width (`w-full`), `py-10`, contenido centrado, glow radial 320px.
   - `BiomarkerEmptyState`: `max-w-[480px]`.
   - El anterior componente `BiomarkerAlert` (borde naranja con string genérico) fue eliminado.

4. LISTA DE INGREDIENTES:
   - Cada ingrediente es una Card expandible (shadcn Accordion):
     - Header: nombre + badge de status (Approved/Banned/Restricted/Under Review)
       con color matching semáforo + confidence_score como barra de progreso
       pequeña.
     - Si tiene conflicts: badge "N conflictos" en rojo/ámbar.
     - Expanded: muestra cas_number, e_number (en mono), y lista de conflicts
       con severity badge + summary + sources como chips.
   - Ordenar: conflicts HIGH primero, luego MEDIUM, luego LOW, luego sin conflicts.

5. METADATA FOOTER:
   - "Escaneado vía código de barras · hace 30 seg".
   - Botón "Escanear otro".
   - Botón secundario "Reportar error" (placeholder — feature futuro).

ESTADOS:
- Loading inicial: skeleton del hero + 3 skeleton cards de ingredientes.
- Error fetch: fallback card con "No pudimos cargar este scan."
  (el scan ya está persistido, usar /scan/history/[id] idealmente).
- ingredients[] vacío (GRAY): mensaje específico "No identificamos
  ingredientes en la etiqueta. Intenta con otra foto."

AVATAR DEL SEMÁFORO:
Al lado del círculo color + icono + label, mostrar el avatar PNG correspondiente
(120×120, animate-pulse-glow) con alt="" + aria-hidden (es decorativo):
- semaphore=GRAY   → /avatars/gray.png
- semaphore=BLUE   → /avatars/blue.png
- semaphore=YELLOW → /avatars/yellow.png
- semaphore=ORANGE → /avatars/orange.png
- semaphore=RED    → /avatars/red.png

COMPONENTES SHADCN/UI NECESARIOS:
- Card, Badge, Accordion, Progress, Alert, Separator, Button.

TOKENS (dark-only):
- Background: #080C07 con hex-grid + scanlines heredados.
- Hero semáforo — colores ajustados para dark (WCAG AA):
  GRAY #A8B3A7 / BLUE #60A5FA / YELLOW #FACC15 / ORANGE #FB923C / RED #F87171.
- Hero: card bs-card con borde del color del semáforo (reemplaza el verde genérico
  rgba(semaphore-color, 0.4) como border), glow del mismo color.
- Ingredientes accordion: border-bottom rgba(74,222,128,0.1), hover bg #0D1310.
- CAS / E-number: JetBrains Mono, color #6B8A6A.
- Severity badges: HIGH → bg rgba(248,113,113,.15) border #F87171 text #F87171;
  MEDIUM → ámbar análogo; LOW → teal análogo.
- Font sans: Space Grotesk. Font mono: JetBrains Mono.

RESPONSIVE:
- Mobile: todo stacked vertical, hero 100% ancho, ingredientes full-width.
- Desktop ≥1024px: layout 2 columnas — izquierda: hero + explicación fijo
  (sticky top-8); derecha: lista de ingredientes scrollable.

TONO: informativo pero nunca alarmista. Usa lenguaje científico cuando
aplique (CAS, E-numbers) pero SIEMPRE con traducción humana. El usuario
no es médico ni toxicólogo — es un adulto preocupado por su salud que
necesita decidir en 10 segundos si comer o no comer esto.

ACCESIBILIDAD:
- aria-live="polite" en el hero del semáforo (anuncia color al cambiar).
- Colores nunca solos — siempre icono + label textual + avatar PNG aria-hidden.
- Focus visible en accordions.

---

### Pantalla 6 — Biosync Upload (`/biosync`) ✅ REESCRITA (flujo PDF)

ROUTE: `/biosync`

CONTEXTO: el usuario sube su PDF de laboratorio (Chopo, Salud Digna, Olab, etc.)
para que el análisis de productos considere su perfil personal. El OCR de Gemini
extrae los biomarcadores automáticamente; el usuario revisa antes de persistir.

DATA FLOWS:
- `POST /biosync/extract` → `BiomarkerExtractionResult` (no persiste, pendiente revisión).
- `POST /biosync/upload` → `BiomarkerUploadRequest { biomarkers: list[Biomarker], lab_name, test_date }`.
- Encripta con AES-256 y guarda con TTL 180 días.

TRES ESTADOS (no tabs — flujo lineal):

**Estado A: Upload**
- Banner de status (has_data=true → ámbar; 404 → info "Sin biomarcadores activos").
- `<AvatarGlow variant="gray" size={96} intensity="soft" />` al lado del dropzone.
- Dropzone: acepta `application/pdf`, máx 10 MB. Copy: "Sube tu PDF de laboratorio".
  Subcopy: "Aceptamos Chopo, Salud Digna, Olab y otros."
- Card de privacidad (ShieldCheck verde + 4 bullets AES/180d/no-share/delete).
- Click/drop → POST `/biosync/extract` → pasa a Estado B.

**Estado B: Loading (analizando)**
- Progress bar indeterminada + copy "Analizando tu PDF con IA…" (mono).
- Subtexto: "~10 segundos. No estamos guardando nada todavía."
- `<AvatarGlow variant="blue" size={80} intensity="strong" />` animado.

**Estado C: Review (post-OCR)**
- Header: "Revisa los valores extraídos" + chip `lab_name` y `test_date`.
- Avatar dinámico según clasificación agregada de los biomarcadores extraídos:
  - Todos normal → `variant="blue"` + "Todo se ve bien por ahora."
  - 1 fuera de rango → `variant="yellow"` + "Encontramos algunos valores fuera de rango."
  - 2+ fuera de rango → `variant="orange"` + misma frase.
  - Animación `pulse-glow` continua, suave.
- Tabla editable: Biomarcador · Valor (input numérico) · Unidad · Rango referencia (badge "lab"/"canónico") · Clasificación (badge color).
- Botón "Eliminar fila" por biomarcador.
- Botón "Agregar biomarcador" (dropdown con taxonomía canónica).
- Botón primario "Confirmar y guardar" → POST `/biosync/upload` → toast + redirect `/`.
- Botón outline "Subir otro PDF" → vuelve al Estado A.

**Eliminado**: tabs Manual/CSV, BiomarkerField, CSVPreviewTable, handleAddCustomField.

AVATAR BIOSYNC:
- Estado A (espera): `gray.png` con glow azul suave (`AvatarGlow`).
- Estado B (procesando): `blue.png` con glow intenso.
- Estado C (review): avatar dinámico `blue`/`yellow`/`orange` según resultado.

TOKENS (dark-only):
- Background: #080C07 con hex-grid + scanlines heredados.
- Avatar glow: animación `avatar-glow-pulse-kf` en `globals.css` (custom props CSS por color).
- Dropzone: border dashed rgba(74,222,128,0.3), hover rgba(74,222,128,0.6).
- Banner has_data: border #F59E0B, bg rgba(245,158,11,.08), text #F59E0B.
- Privacy card: bg rgba(74,222,128,.05), border rgba(74,222,128,.15), ShieldCheck verde.
- Tabla review: border-bottom rgba(74,222,128,.1), hover bg rgba(74,222,128,.04).
- Badge "lab": bg rgba(96,165,250,.15) text #60A5FA. Badge "canónico": bg rgba(107,138,106,.15) text #6B8A6A.
- Botón primario: bs-glow-green, JetBrains Mono.

RESPONSIVE:
- Mobile: flujo vertical completo.
- Desktop ≥1024px: layout 2 columnas — área principal 2/3, privacy card 1/3 sticky.

TONO: tranquilizador en Estado A, activo en B, confirmatorio en C.
El usuario está compartiendo datos médicos — la UI proyecta competencia y respeto.

---

### Pantalla 7 — Historial de Scans (`/history`)

ROUTE: `/history`

DATA SHAPE: array de ScanHistory entries (endpoint futuro GET /scan/history):
[
  { id, product_barcode, product_name, semaphore, conflict_severity,
    source: "barcode"|"photo", scanned_at }
]

LAYOUT:
- Header con título "Historial" + contador "N escaneos en los últimos 30 días".
- Filtros: Tabs con counts: "Todos (N)" / "RED (N)" / "ORANGE (N)" /
  "YELLOW (N)" / "BLUE (N)" / "GRAY (N)".
- Input de búsqueda arriba: filtra por product_name.
- Lista de cards — cada card con:
  - Thumbnail del semáforo (círculo color + icono, 40px).
  - Nombre producto + barcode en mono pequeño.
  - Fecha relativa ("hace 2h") + tooltip con fecha absoluta.
  - Chip con source ("Barcode" o "Foto").
  - Chevron para abrir detalle (`/scan/[id]`).
- Agrupado por día ("Hoy", "Ayer", "Hace 3 días", "Abril 2026").

ESTADOS:
- Loading: 10 skeletons.
- Empty (sin scans): ilustración + CTA "Escanear primer producto".
- Empty con filtro activo: "Sin resultados para este filtro."

RESPONSIVE:
- Mobile: lista full-width.
- Desktop: lista max-width 720px centrada.

AVATAR HISTORIAL:
- Empty state sin scans: welcome.png (120×120) + CTA "Escanear primer producto".
- Thumbnails del semáforo en cada fila: NO usar PNG — usar solo círculo color
  + icono Lucide 20px (más compacto para listas densas).

TOKENS (dark-only):
- Background: #080C07 con hex-grid + scanlines heredados.
- Filas: bg transparente, hover bg rgba(74,222,128,.04), border-bottom
  rgba(74,222,128,.08).
- Thumbnail semáforo: círculo 40×40, color de fondo semáforo con opacidad 20%,
  icono Lucide color sólido del semáforo. Colores dark: B.1 de este plan.
- Input búsqueda: misma estética que login (border rgba(74,222,128,.15)).
- Tabs filtro: shadcn, cada tab con count badge (fondo del color del semáforo
  con opacidad 20%).
- Agrupadores de día: JetBrains Mono 10px UPPERCASE, color #6B8A6A.
- Font sans: Space Grotesk. Font mono: JetBrains Mono.

RESPONSIVE:
- Mobile: lista full-width.
- Desktop: lista max-width 720px centrada.

TONO: utilitario, rápido, legible. Densidad alta. Sin decoración innecesaria.

---

### Pantalla 8 — Error / Empty / Loading globales

Los 3 estados globales compartidos de BioShield AI:

1. Error 500 / red — página completa:
   - Icono grande ServerCrash.
   - "Algo salió mal."
   - Texto "Intentamos pero no pudimos. Puedes reintentar o volver al inicio."
   - Botón "Reintentar" + botón secundario "Ir al inicio".

2. Sesión expirada (401 después de refresh fallido):
   - Modal/dialog centrado.
   - "Tu sesión expiró por inactividad."
   - Botón "Entrar de nuevo" → redirige a /login.

3. Loading skeleton base (reusable):
   - Skeleton de line, card, y list-item. 3 variantes.

AVATAR ESTADOS GLOBALES:
- Error 500: support.png (120×120) encima del mensaje de error.
- Sesión expirada: gray.png (100×100, sin animate-wobble) en el dialog. (**No main.png** — corregido en impl.)
- Loading skeleton: no avatar — solo skeleton shimmer genérico.

TOKENS (dark-only):
- Background: #080C07 con hex-grid + scanlines heredados.
- Error 500: page centrada, soporte.png arriba, título Space Grotesk bold 2xl,
  copy JetBrains Mono 13px color #6B8A6A, botones con bs-glow-green.
- Dialog sesión expirada: bg #0D1310, border rgba(74,222,128,.18),
  borde-radius 18px, backdrop-blur. Botón primary #4ADE80.
- Skeleton: bg rgba(74,222,128,.06), shine con gradiente verde muy sutil.
  NO usar grises genéricos — el shimmer debe sentirse parte del sistema dark.
- Font sans: Space Grotesk. Font mono: JetBrains Mono.

TONO: humano, sin tecnicismos. "Algo salió mal" > "Error HTTP 500".
El fondo con glows y hex-grid persiste incluso en error — la marca no se rompe.

---

### Apéndice — Lecciones aprendidas del login (fusión desde E.1)

Reglas que Claude Code debe respetar al implementar cualquier pantalla:

1. **Avatares:** usar nombres reales del repo — `success.png`, `support.png`, `progress.png`, `welcome.png`, `profile.png`, `main.png` + semáforos `gray/blue/yellow/orange/red.png`. No inventar nombres tipo `mascot-happy.png` / `mascot-loading.png`.
2. **JetBrains Mono** ya está cargada vía `next/font/google` en `app/layout.tsx` como `--font-jetbrains-mono`. No usar `@import` en CSS.
3. **Tokens** viven en `frontend/app/globals.css` y se consumen con clases Tailwind (`bg-brand-green`, `bg-surface`, `text-foreground`, etc.). No duplicar en `tokens/design-tokens.json` ni en archivos paralelos.
4. **Data fetching:** usar `useMutation` / `useQuery` de TanStack Query dentro del componente, llamando funciones de `lib/api/*`. Nada de hooks custom tipo `useLoginForm`.
5. **Dashboard** está en `/` (grupo `(app)/page.tsx`). `router.push('/')`, NUNCA `'/dashboard'`.
6. **Nombres de tokens** Tailwind: `--brand-green`, `--brand-amber`, `bg-surface`. No inventar `--green` / `--amber` sueltos.

---

## Fase D — Implementación de cada item 7.1-7.9

### 7.0 · Componentes compartidos (on-demand)

**Regla operativa:** el componente nace inline en la pantalla origen. Cuando una segunda pantalla lo necesite, se extrae a `components/<grupo>/<Componente>.tsx` con la API más chica posible. **No crear componentes preventivamente.**

Plan de emergencia de componentes, en el orden en que las pantallas pendientes los exigen:

| Componente | Pantalla origen | Extraer a `components/` cuando | Tokens / API clave |
|---|---|---|---|
| `BarcodeScanner` | `/scan` tab barcode | — (único consumer) | video + overlay recortado + laser `animate-scan-line` + `@zxing/browser` |
| `PhotoCapture` | `/scan` tab foto | — (único consumer) | dropzone `rgba(74,222,128,.3)` + `capture="environment"` + base64 encoding <10MB |
| `OFFContributeToggle` **[FASE 2]** | `/scan` tab foto | — | shadcn Switch + Tooltip + copy ODbL + `POST /scan/contribute` |
| `SemaphoreHero` | `/scan/[id]` | Nunca por ahora — un solo consumer | círculo 120px color semáforo + icono Lucide + avatar PNG lateral + `animate-pulse-glow` |
| `IngredientAccordion` | `/scan/[id]` | — | shadcn Accordion + badge status + barra confidence + badge "N conflictos" |
| `ConflictRow` | `/scan/[id]` (dentro de IngredientAccordion) | — | severity badge HIGH/MEDIUM/LOW + summary + sources chips |
| `AvatarGlow` | `/biosync` (Estado A/B/C) + `/scan/[id]` (InsightCards) | **Inmediatamente** — nació como componente compartido | `variant: gray\|blue\|yellow\|orange\|red`, `size?: number`, `intensity?: soft\|medium\|strong`; animación CSS `avatar-glow-pulse-kf` con custom props |
| `InsightCard` | `/scan/[id]` — sección "Para ti" | — | `<AvatarGlow>` 72px + friendly_title + friendly_explanation + friendly_recommendation + chips de ingredientes |
| `BiomarkerEmptyState` | `/scan/[id]` — sin biomarcadores | — | `<AvatarGlow variant="gray" size={56} intensity="soft">` + link a /biosync; reemplaza el antiguo `BiomarkerAlert` |
| `BiomarkerField` | eliminado de `/biosync` — flujo manual removido | — | — |
| `BiomarkerCSVUpload` | eliminado de `/biosync` — flujo CSV removido | — | — |
| `PrivacyCard` | `/biosync` sidebar | Si se reusa en `/register` se extrae con la API existente | `ShieldCheck` verde + 4 bullets en JetBrains Mono |
| `SemaphoreBadge` | `/` Dashboard (recent scans) **o** `/history` (lo que llegue primero) | **Inmediatamente** al aparecer en el segundo consumer | círculo 40px bg `rgba(color,.2)` + icono Lucide 20px color sólido |
| `MascotAvatar` | cualquier empty state que use PNG con `animate-wobble` / `bs-mascot-glow` | Si un segundo consumer pide tamaño distinto | props `src` + `size` + `animate` + `glow` (boolean) |
| `HistoryRow` | `/history` | — | fila compacta + `SemaphoreBadge` + nombre + barcode mono + fecha relativa + chip source + chevron |
| `DayGroupHeader` | `/history` | — | JetBrains Mono UPPERCASE 10px `#6B8A6A` tracking 0.1em |
| `FilterTabs` (por semáforo) | `/history` | Si Dashboard añade filtros | shadcn Tabs + count badges `rgba(color,.2)` |
| `PasswordStrengthBar` | `/register` ✅ inline | Solo si otra pantalla introduce fuerza de password | 3 tramos rojo `#F87171` / ámbar `#F59E0B` / verde `#4ADE80` |

Orden de aparición esperado: Scanner (7.3) → componentes scanner + OFF toggle. Resultado (7.4) → SemaphoreHero, IngredientAccordion, ConflictRow, BiomarkerAlert. Biosync (7.5) → BiomarkerField, BiomarkerCSVUpload, PrivacyCard. Dashboard (7.7) → SemaphoreBadge (extracción inmediata al llegar a History). Historial (7.8) → HistoryRow, DayGroupHeader, FilterTabs.

### 7.1 · App Router + Tailwind + TanStack Query + Zustand

**Archivos:**
- `frontend/app/layout.tsx` — `<QueryClientProvider>` + fuentes (Pacifico/SpaceGrotesk/JetBrains). ✅ IMPLEMENTADO
- `frontend/app/globals.css` — tokens dark-only + hex-grid + semáforo ajustado. ✅ IMPLEMENTADO
- `frontend/lib/stores/auth.ts` — Zustand store con `user`, `setUser`, `logout`. ✅ IMPLEMENTADO
- `frontend/lib/api/client.ts` — fetcher con refresh automático (descrito en A.2). ✅ IMPLEMENTADO (emite evento `session-expired` en vez de redirect duro)

**Checks de éxito:**
- `pnpm dev` arranca en :3000.
- Dark-only forzado: `<html class="dark">` — no hay ThemeToggle (eliminado del plan).
- TanStack Query devtools visible en dev.
- Fondo con hex-grid + scanlines visible en cualquier ruta.

**Nota sobre la desviación del doc:** el review §7 dice "zustand/SWR". Cambiamos SWR → TanStack Query porque tiene mejor DX para mutations, optimistic updates, y el cache por barcode (item 7.6) es trivial con `queryKey: ["scan", barcode]`. Zustand se queda para client state (auth).

### 7.2 · Auth UI consumiendo JWT HTTP-only ✅ IMPLEMENTADO

**Archivos:**
- `frontend/app/(auth)/login/page.tsx` ✅ — spec: Fase C — Pantalla 1 (handoff en `docs/design/login/`).
- `frontend/app/(auth)/register/page.tsx` ✅ — spec: Fase C — Pantalla 2.
- `frontend/lib/api/auth.ts` ✅ — `login` (raw fetch, no interceptor 401), `register`, `logout`, `refresh`.
- `frontend/app/(app)/layout.tsx` ✅ — navbar + SessionExpiredDialog (escucha evento `session-expired`). Avatar `profile.png` eliminado del navbar (limpieza de header).
- `frontend/proxy.ts` ✅ (renombrado de middleware.ts — Next.js 16) — chequea cookie `access_token`.

### 7.2b · Dashboard placeholder ✅ IMPLEMENTADO
- `frontend/app/(app)/page.tsx` ✅ — placeholder hasta implementación real en 7.7 (spec: Fase C — Pantalla 3)

### 7.2c · Global UI states ✅ IMPLEMENTADO
- `frontend/components/SessionExpiredDialog.tsx` ✅ — gray.png (no main.png) + "entrar de nuevo" → `window.location.href = "/login"` (hard redirect, no router.push). `onInteractOutside` + `onEscapeKeyDown` previenen cierre accidental del modal.
- `frontend/components/ErrorPage.tsx` ✅ — support.png + retry + ir al inicio
- `frontend/app/error.tsx` ✅ — Next.js error boundary global
- `frontend/components/Skeletons.tsx` ✅ — SkeletonCard / SkeletonRow / SkeletonHero (shimmer verde)

**Checks de éxito:**
- Registro → auto-login → dashboard.
- 401 en cualquier request → reintento con `/auth/refresh` → si ok, sigue; si no, redirect login.
- Logout limpia cookies backend-side + Zustand store.

### 7.3 · Scanner UI ✅ IMPLEMENTADO

**Archivos:**
- `frontend/app/(app)/scan/page.tsx` ✅ — spec: Fase C — Pantalla 4.
- `frontend/components/scanner/BarcodeScanner.tsx` ✅ — @zxing/browser con controls.stop() cleanup, overlay recortado, laser scan-line, flash detección 300ms.
- `frontend/components/scanner/PhotoCapture.tsx` ✅ — dropzone + capture="environment" (mobile) + base64 + validación 10MB.
- `frontend/components/scanner/OFFContributeToggle.tsx` — marcador [FASE 2], pendiente. Comentado en scan/page.tsx.
- `frontend/lib/api/scan.ts` ✅ — ya existía con `scanBarcode`, `scanPhoto`, `contributeToOff`.
- `frontend/app/(app)/scan/[id]/page.tsx` ✅ — placeholder que lee del cache de TanStack Query; implementación completa en 7.4.

**Decisiones de implementación:**
- URL param = `product_barcode` (siempre presente en `ScanResponse`). Cache key: `["scan", barcode]`.
- Cache check ANTES de llamar al backend (implementa 7.6 sin staleTime explícito — si está en cache navega directo).
- `controls.stop()` para cleanup de @zxing (no `reader.reset()` — no existe en v0.1.5).
- Avatar `progress.png` en loading de foto (`animate-pulse-glow bs-mascot-glow`), `support.png` en permiso denegado.
- **pseudo_barcode de foto:** formato `photo-{uuid16}` con guión (no `photo:` — los dos puntos hacen que Next.js interprete `photo:` como URL scheme, corrompiendo el query string `?via=photo`).
- **Navegación post-foto:** `router.push(\`/scan/${encodeURIComponent(data.product_barcode)}?via=photo\`)` — `encodeURIComponent` hace explícito el path segment.
- **Error type `error_process`:** estado para 400/5xx del servidor (mensaje: "El servidor no pudo procesar la imagen. Intenta de nuevo."), diferenciado de `error_read` (422) y `error_net` (network).

**Dependencia extra (Fase 2):**
- Ejecutar `pnpm dlx shadcn@latest add switch tooltip` (para el toggle OFF + info icon tooltip).

**Checks de éxito:**
- Barcode real (Nutella 3017620422003) → navega a `/scan/[id]` con semaphore="YELLOW".
- Foto de etiqueta MX (usar `backend/test_images/*.jpeg` como fixtures) → pipeline completo.
- 404 en barcode muestra modal que cambia a photo tab.
- Permiso cámara denegado → fallback a input manual sin romper.
- [FASE 2] Toggle "Contribuir a OFF" visible solo en photo tab, off por defecto.
- [FASE 2] Con toggle on + scan photo exitoso → fetch `POST /scan/contribute` con `consent: true` → toast success "Gracias por contribuir".
- [FASE 2] Con toggle off → no se dispara `/scan/contribute` bajo ninguna circunstancia.
- [FASE 2] Si `/scan/contribute` retorna 5xx → toast warning no bloqueante; resultado sigue visible.

### 7.4 · Semáforo visual con detalles de conflict ✅ IMPLEMENTADO

**Archivos:**
- `frontend/app/(app)/scan/[id]/page.tsx` ✅ — spec: Fase C — Pantalla 5. Actualizado con sección "Para ti".
- `SemaphoreHero` ✅ — inline en la pantalla.
- `IngredientAccordion` + `ConflictRow` ✅ — inline, un único consumer.
- `ParaTiSection` ✅ — fila dedicada full-width debajo del grid; carousel scroll-snap con tabs en header.
- `DiagnosticInsightCard` ✅ — inline; incluye `BiomarkerRangeBar` (animado), `ImpactArrows`, `StatusPill`.
- `BiomarkerRangeBar` ✅ — track con zonas low/normal/high + marker dot animado (halo + ring + dot appear).
- `BiomarkerEmptyState` ✅ — inline; `max-w-[480px]`; reemplaza el antiguo `BiomarkerAlert`.
- `BiomarkerClearState` ✅ — inline; card full-width (`w-full py-10`), contenido centrado, sin wrapper limitante.
- `AvatarGlow` ✅ — extraído a `components/AvatarGlow.tsx` (compartido con /biosync). Props: `variant`, `size`, `intensity`.
- `SemaphoreBadge` ✅ — extraído a `components/semaphore/SemaphoreBadge.tsx` al aparecer en Dashboard (7.7).
- `PhotoExpiredState` ✅ — inline: estado fallback cuando `viaPhoto=true` y el cache está vacío.

**Decisiones de implementación:**
- `decodeURIComponent(rawId)` en el hook `useParams` — normaliza el barcode para hacer match con la cache key (que usa el valor sin encodear del response del backend).
- Glow color: `@keyframes pulse-glow` en globals.css tiene `drop-shadow` hardcodeado verde. Solución: `animate-pulse` en el wrapper (solo opacity) + `filter: drop-shadow` inline en el mismo wrapper. No usar `animate-pulse-glow` sobre el avatar — sobreescribiría el color dinámico.
- `viaPhoto`: lee `useSearchParams().get("via") === "photo"`. Si `isError || !data`: `viaPhoto ? <PhotoExpiredState /> : <NoCacheState />`.
- Para Ti layout: hero column reducida a `300px` (era `380px`); Para Ti sale del sticky left column y pasa a Row 2 separada por `border-top rgba(green,.08)`.
- Carousel Para Ti: `overflow-x-auto + snap-x snap-mandatory` en lugar de `translateX` — el swipe nativo del browser maneja mobile; `trackRef.scrollTo` para navegación desktop via dots.
- `scrollbarWidth: none` cast como `React.CSSProperties` para evitar error TypeScript (`WebkitOverflowScrolling` es non-standard).

**Checks de éxito:**
- Los 5 colores se renderizan con glow del color correcto (amarillo para YELLOW, no verde).
- Accordion expande y muestra CAS/E-number en mono + conflicts ordenados por severity.
- Alertas de biomarcadores aparecen solo si `semaphore === "ORANGE"`.
- Accesibilidad: navegar con teclado + screen reader (macOS VoiceOver) anuncia semáforo.
- Foto scan: `progress.png` → loading → navega a `/scan/photo-abc123?via=photo` → resultado visible.
- Foto scan en sesión nueva (cache vacío): muestra `PhotoExpiredState` (no `NoCacheState`).

### 7.5 · Biosync UI ✅ REESCRITA (flujo PDF)

**Archivos:**
- `frontend/app/(app)/biosync/page.tsx` ✅ — reescrita con flujo PDF: tres estados (upload / loading / review). Eliminados: Tabs, BiomarkerField, CSVPreviewTable, lógica CSV, formulario manual.
- `frontend/components/AvatarGlow.tsx` ✅ — componente compartido nuevo. Variant gray/blue/yellow/orange/red, intensity soft/medium/strong, animación CSS `avatar-glow-pulse-kf`.
- `frontend/app/globals.css` ✅ — añadidos `@keyframes avatar-glow-pulse-kf` y clase `.avatar-glow-pulse` con `prefers-reduced-motion` support.
- `frontend/lib/api/biosync.ts` ✅ — `extractBiomarkers(file: File)` nuevo; `uploadBiomarkers` actualizado a `BiomarkerUploadRequest` estructurado.
- `frontend/lib/api/types.ts` ✅ — tipos nuevos: `Biomarker`, `BiomarkerExtractionResult`, `BiomarkerUploadRequest`, `PersonalizedInsight`, `AvatarVariant`, `CanonicalBiomarker`.
- `frontend/lib/api/client.ts` ✅ — FormData detection para omitir `Content-Type: application/json` en uploads de PDF.

**Checks de éxito:**
- Subir PDF → Estado loading (AvatarGlow blue intenso) → Estado review (tabla editable, avatar dinámico).
- Editar un valor en review → Confirmar → 201 → toast + redirect a `/`.
- PDF >10MB o no-PDF → error 422 con mensaje claro.
- Scan con biomarcadores activos (LDL alto) → producto con grasas trans → semaphore ORANGE + sección "Para ti".

### 7.6 · TanStack Query cache por barcode

**Implementación:**
- `queryKey: ["scan", "barcode", barcode]` con `staleTime: 5 * 60 * 1000` (5 min).
- El cache es por-usuario (React Query por tab/session); persistencia opcional con `@tanstack/query-async-storage-persister` + `localStorage` si queremos offline-friendly.

**Checks de éxito:**
- Escanear mismo barcode 2 veces en <5min → segunda llamada sirve de cache, sin request al backend (devtools lo confirma).
- Forzar refetch con botón "Actualizar" en la pantalla de resultado.

### 7.7 · Dashboard real ✅ IMPLEMENTADO

**Archivos:**
- `frontend/app/(app)/page.tsx` ✅ — hero CTA Escanear, BiosyncCard (has_data + nearExpiry badge ámbar), RecentScans (skeletons + empty state welcome.png + HistoryRow inline).
- `components/semaphore/SemaphoreBadge.tsx` ✅ — extraído inmediatamente (reusado en History 7.8). Props: `color`, `size`, `showLabel`.
- `frontend/lib/api/scan.ts` ✅ — `getScanHistory(limit)` añadido (GET /scan/history — **implementado en backend** en `backend/app/routers/scan.py`; `source` derivado stateless del prefijo `photo-`).
- `frontend/lib/api/types.ts` ✅ — `ScanHistoryEntry` añadido.

**Checks de éxito:**
- Login → dashboard real con hero CTA + estado biosync + últimos 5 scans.
- Sin scans → empty state con `welcome.png` + CTA "escanear primer producto".
- `has_data=true` y `expires_at < 30 días` → badge ámbar en card biosync.
- Skeletons durante loading de scan history.

### 7.8 · Historial de Scans ✅ IMPLEMENTADO

**Archivos:**
- `frontend/app/(app)/history/page.tsx` ✅ — búsqueda por nombre/barcode, FilterTabs con count badges por semáforo, agrupación por día (Hoy/Ayer/Hace N días/Mes YYYY), HistoryItemRow + SemaphoreBadge, 10 skeletons loading, EmptyState welcome.png.
- `SemaphoreBadge` ✅ — reusado de components/semaphore/.
- `HistoryItemRow` + `DayGroupHeader` + filtros ✅ — inline en history/page.tsx.

**Checks de éxito:**
- Lista agrupada por día ("Hoy", "Ayer", "Hace 3 días", "Abril 2026").
- FilterTabs con count por semáforo funcionando.
- Search filtra por `product_name`.
- Empty con filtro activo → "sin resultados para este filtro".
- Chevron → navegar a `/scan/[id]`.

### 7.9 · Polish global (Error / Loading) ✅ IMPLEMENTADO

Pulido de estados globales — el scaffolding (`app/error.tsx`, `ErrorPage.tsx`, `SessionExpiredDialog.tsx`, `Skeletons.tsx`) ya está en 7.2c. Aquí refinamos.

**Archivos:**
- `frontend/app/globals.css` — añadir keyframe `shimmer` para skeleton verde:
  ```css
  @keyframes shimmer {
    0%   { background-position: -200% 0; }
    100% { background-position:  200% 0; }
  }
  ```
- `frontend/components/Skeletons.tsx` — verificar que `SkeletonCard/Row/Hero` usen base `rgba(74,222,128,.06)` + gradiente `linear-gradient(90deg, transparent, rgba(74,222,128,.1), transparent)` + `animation: shimmer 1.5s infinite`. Sin grises.
- `frontend/components/ErrorPage.tsx` — verificar `support.png` 120×120 estático (sin wobble ni glow).
- `frontend/components/SessionExpiredDialog.tsx` — verificar `gray.png` 80×80 estático (no main.png — corregido).

**Checks de éxito:**
- Shimmer verde visible en skeletons, no gris.
- Error boundary (`app/error.tsx`) dispara `ErrorPage` con retry + ir al inicio.
- Session expired dialog se muestra al escuchar `session-expired` event (ya emitido desde `lib/api/client.ts` en 7.1).

---

## Fase E — Verificación end-to-end

Después de implementar, validar con estos casos en navegador real (Chrome + Safari mobile) apuntando a `docker compose up`:

1. **Happy path barcode:**
   - Register → Login → `/scan` → barcode tab → escanear `3017620422003` (Nutella) → `/scan/[id]` muestra semaphore YELLOW con ingredientes + conflicts.
2. **Happy path photo:**
   - `/scan` → photo tab → subir `backend/test_images/1.jpeg` → semaphore computado → detalle correcto.
3. **Orange biomarker match:**
   - `/biosync` → manual → `{ ldl: 150 }` → upload OK.
   - `/scan/barcode` de un producto con grasas trans → semaphore ORANGE con alerta "Tu LDL está en 150 y este producto contiene grasas trans".
4. **Cache TanStack Query:**
   - Escanear mismo barcode 2 veces en <5min → network devtools confirma cache hit.
5. **Refresh 401:**
   - En dev tools: borrar cookie `access_token` (dejar `refresh_token`) → hacer scan → frontend llama `/auth/refresh` automáticamente → scan procede sin redirect.
6. **Logout:**
   - Menu dropdown → logout → cookies borradas → redirect `/login` → `/scan` directo redirige de vuelta a `/login`.
7. **Accesibilidad:**
   - VoiceOver macOS lee semáforo correctamente.
   - Navegar flujo completo solo con teclado (Tab/Enter/Escape).
8. **Rate limit:**
   - 11 requests a `/auth/login` en <60s → frontend muestra toast "Demasiados intentos. Espera 60s.".

---

## Archivos críticos — resumen

**Backend (ya existen, solo lectura para mirror de tipos):**
- `backend/app/schemas/models.py` — source of truth para `frontend/lib/api/types.ts`.
- `backend/app/routers/{auth,scan,biosync}.py` — contracts.
- `backend/app/services/analysis.py` — BIOMARKER_RULES que alimentan los hints del form de biosync.
- `backend/app/main.py` línea 24-30 — CORS (verificar `ALLOWED_ORIGINS`).

**Frontend:**
- `frontend/package.json`, `frontend/next.config.ts`, `frontend/tailwind.config.ts`.
- `frontend/app/layout.tsx`, `frontend/app/globals.css`. ✅
- `frontend/lib/api/{client,auth,scan,biosync,types}.ts`. ✅ (salvo `getScanHistory` pendiente en 7.7)
- `frontend/lib/stores/auth.ts`. ✅
- 8 archivos de página en `frontend/app/(auth)/**` y `frontend/app/(app)/**` (2 de 8 ✅ login+register).
- 15-20 componentes en `frontend/components/**` (core auth + globals ✅; scanner/semaphore/ingredients/biosync pendientes — regla on-demand 7.0).

**Docs:**
- `docs/design/tokens.md` — canónico de tokens. ✅
- `docs/design/login/**` — handoff histórico del login. ✅ (no tocar)
- `docs/design/README.md` — opcional, índice con links a `docs/design/login/` y `tokens.md`. **NO se crea doc por pantalla** (decisión: sin handoff para pantallas nuevas).
- `docs/reviews/18-04.md` — actualizar §13 con cierre de Fase 7 al terminar.

**DevOps:**
- `docker-compose.yml` — agregar servicio `frontend` (Fase A.4).
- `.github/workflows/ci.yml` — agregar job `frontend-build` (pnpm install + build + lint + typecheck).

---

## Estimación de esfuerzo

| Fase | Esfuerzo | Dependencias |
|---|---|---|
| A — Setup monorepo | ✅ done | — |
| B — Design tokens | ✅ done | — |
| C — Specs por pantalla | ✅ redactadas en este plan | — |
| D.7.0 — Componentes compartidos | on-demand con cada pantalla | — |
| D.7.1 / 7.2 / 7.2b / 7.2c — Infra + Auth + Globals | ✅ done | — |
| D.7.3 — Scanner UI + OFF toggle [Fase 2] | ✅ done | — |
| D.7.4 — Resultado scan + semáforo + ingredients | ✅ done | — |
| D.7.5 — Biosync UI (reescrita: flujo PDF + AvatarGlow) | ✅ done | — |
| D.7.6 — Cache TanStack Query | ✅ done (embebido en 7.3) | — |
| D.7.7 — Dashboard real | ✅ done | — |
| D.7.8 — Historial | ✅ done | — |
| D.7.9 — Polish global (shimmer + ErrorPage pulido) | ✅ done | — |
| E — Verificación E2E | pendiente | Todo lo anterior |
| **Total pendiente** | **~0.5-1 día (solo E2E)** | Backend listo |

---

## Riesgos y mitigaciones

1. **Drift entre tipos FE y schemas BE.**
   Mitigación: generar tipos con `openapi-typescript` contra `/openapi.json` en CI. Bloqueante si falla.

2. **Permisos de cámara en iOS Safari.**
   Mitigación: Fallback input manual de barcode siempre disponible; PhotoCapture acepta file upload sin cámara.

3. **Free tier de Gemini agotado en dev** (§9.3 del review).
   Mitigación: mockear `POST /scan/photo` con fixture de ScanResponse en desarrollo FE; scan real contra staging con tier pagado.

4. **Cookies cross-origin en producción.**
   Mitigación: mismo dominio FE+BE con subdominio (`app.bioshield.ai` + `api.bioshield.ai`) y `SameSite=Lax` (ya configurado en backend). Si despliegue inicial es Vercel (FE) + Render (BE) en dominios distintos, requiere `SameSite=None; Secure`. Verificar en staging antes de prod.

5. **Convergencia visual más lenta sin intermediario de diseño.**
   Mitigación: `docs/design/login/README.md` sigue siendo plantilla visual viva; tokens inmutables (no inventar colores ni glows); iteración incremental con revisión de Alberto en `pnpm dev` antes de cerrar cada pantalla; "Lecciones aprendidas del login" al final de Fase C previenen desviaciones conocidas (avatares, fuentes, rutas, tokens).

6. **Pantallas nuevas divergen del look&feel del login sin querer.**
   Mitigación: cada pantalla consume utilidades existentes (`bs-card`, `bs-glow-green`, `bs-glow-green-strong`, `bs-corner-{tl,tr,bl,br}`, `bs-input-focus`, `bs-mascot-glow`). Corner accents + glow verde son firma visual no negociable para `/login` y `/register`; en pantallas app (Scanner, Resultado, Biosync, Dashboard, History) aplicar corner accents solo al CTA principal o hero card, no a todo.
