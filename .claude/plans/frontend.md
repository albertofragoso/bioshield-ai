# Fase 7 — Frontend BioShield AI: Diseño en claude.ai/design + implementación Next.js

## Context

El backend MVP está **cerrado y verde** (90 tests passing, 11 endpoints expuestos, pipeline LangGraph funcional con semáforo 5 colores, OCR Gemini Vision validado con 13 etiquetas MX reales). El bloqueante principal del proyecto — documentado en `docs/reviews/18-04.md §5` (red flag #5) — es la **ausencia de UI**: sin frontend no hay dogfood end-to-end, no se puede entrevistar usuarios, y el PRD Fase 2 (Retail Integration) y Fase 3 (Reality Engineering) quedan bloqueados por falta de signal de uso real.

Fase 7 cubre 6 items (7.1-7.6) del review. Este plan los descompone en:
1. **Setup monorepo `/frontend`** (Next.js 15 + Tailwind + shadcn/ui + TanStack Query + Zustand).
2. **Design system tokens** (semáforo, typography, look médico/confiable).
3. **8 pantallas**, cada una con un prompt completo y autocontenido para pegar en **https://claude.ai/design** e iterar visualmente.
4. **Handoff** — portar componentes generados a `/frontend` y cablearlos contra el backend real.
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
- **Prompts de diseño (claude.ai/design):** `docs/design/README.md`
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

## Fase C — Prompts para claude.ai/design (1 por pantalla)

**Instrucciones de uso:** copia cada prompt en claude.ai/design. Itera hasta que te convenza el look. Guarda screenshot en `docs/design/<pantalla>.png` + link a la sesión. Luego usa el componente generado como referencia visual al implementar en `/frontend/app/...`.

Cada prompt sigue la misma estructura: **producto → pantalla → data → estados → tokens → responsive**.

---

### Prompt 1 — Login (`/login`) ✅ DISEÑADO

> Diseño completo en `docs/design/login/`. Tokens y referencia visual en
> `docs/design/login/README.md` + `design-tokens.json`. Este prompt queda como
> registro — los siguientes lo toman como base visual.

```
Diseña la pantalla de login de BioShield AI, una app que escanea etiquetas
nutricionales y cruza aditivos con biomarcadores de sangre del usuario.

PANTALLA: Login
ROUTE: /login
USUARIO TARGET: adultos 25-55 en México con preocupaciones de salud
(colesterol, diabetes, hipertensión).

DATA SHAPE (request a POST /auth/login):
{ email: string, password: string (min 8 chars) }

RESPONSE (éxito 200):
{ access_token, refresh_token, token_type: "bearer", expires_in: 1800 }
Nota: los tokens se guardan como HTTP-only cookies automáticamente;
el frontend NO los maneja.

ESTADOS A CUBRIR:
- Idle: formulario limpio.
- Loading: botón con spinner, campos deshabilitados.
- Error 401: alerta roja "[ERROR_401] Credenciales inválidas. Verifica tus datos."
- Error 429: alerta ámbar "[ERROR_429] Demasiados intentos. Espera 60 segundos."
- Error red: toast "sin_conexion_al_servidor" con icono WifiOff.

COMPONENTES:
- Card centrada, max-width 420px, border-radius 18px.
- Avatar mascota (piña con escudo ADN, PNG 140×140, animate-wobble, glow verde).
- Wordmark: "BioShield" en Pacifico 28px verde #4ADE80 + "AI" en Space Grotesk
  bold 26px amber #F59E0B.
- Tagline en JetBrains Mono 9.5px: "hack your nutrition ✦ protect your biology".
- Input email (icon Mail), input password (icon Lock + toggle Eye/EyeOff).
  Labels en JetBrains Mono UPPERCASE 10px.
- Botón primario "⟶ entrar" (idle) / spinner + "verificando…" (loading).
  JetBrains Mono 13px, tracking 0.12em, background rgba(74,222,128,.15),
  border #4ADE80, border-radius 10px.
- Link "¿Olvidaste tu contraseña?" — JetBrains Mono 10.5px, color #2DD4BF.
- Link "sin cuenta? regístrate →" — JetBrains Mono 11px, "regístrate" en #F59E0B.
- Metadata footer: "v1.0.0 · /login · POST /auth/login" (JetBrains Mono 9px,
  color rgba(74,222,128,.2)).

TOKENS DE MARCA (dark-only, sin variante light):
- Background global: #080C07 con hex-grid SVG + scanlines overlay + glow radial verde.
- Card: background #0D1310, border rgba(74,222,128,.18), border-radius 18px,
  box-shadow glow verde, backdrop-blur 20px.
- Corner accents: 4 esquinas, 60×60px, borde rgba(74,222,128,.35).
- Primary green: #4ADE80 — CTA, bordes focus, glows.
- Amber: #F59E0B — wordmark "AI", links registro.
- Teal: #2DD4BF — links secundarios.
- Error: #F87171 (alert 401) / #FCD34D (alert 429).
- Font display: Pacifico 400 (solo wordmark).
- Font body: Space Grotesk 300–700.
- Font mono: JetBrains Mono 400–700.

RESPONSIVE:
- Mobile 375px: card full-width, padding 28px 16px 24px.
- Desktop: card centrada max-width 420px, padding 40px 36px 36px.

TONO VISUAL: biotech hacker — oscuro, glows bioluminiscentes, scanner sci-fi.
Limpio y profesional pero con identidad visual fuerte. El usuario confía
porque parece que la tecnología es seria, no porque sea un formulario estéril.
```

---

### Prompt 2 — Register (`/register`)

```
Diseña la pantalla de registro de BioShield AI. Misma estética que el login
ya diseñado: dark-only, hex-grid + scanlines + glows verdes bioluminiscentes,
card con corner accents, avatar mascota piña con escudo ADN.

PANTALLA: Registro
ROUTE: /register

DATA SHAPE (POST /auth/register):
{ email: string (valid email), password: string (min 8 chars) }

RESPONSE (éxito 201): UserResponse { id: uuid, email, created_at }
Después del 201, el frontend hace automáticamente POST /auth/login.

ESTADOS:
- Idle, Loading, Error 409 "[ERROR_409] Email ya registrado",
  Error validación (password < 8 chars → hint inline bajo el campo), Error red.

COMPONENTES:
- Misma estructura de card que Login: background #0D1310, border-radius 18px,
  corner accents, glow superior, avatar mascota con animate-wobble.
- Input email + input password con indicador de fuerza (barra bajo el campo:
  #F87171 corta / #F59E0B media / #4ADE80 fuerte — según longitud y variedad).
- Checkbox "acepto términos y política de datos médicos" (required).
  Estilo: JetBrains Mono 11px, color #6B8A6A.
- Párrafo de privacidad (2 líneas, LOAD-BEARING — no esconder):
  "Tus biomarcadores se encriptan con AES-256 y se borran automáticamente
   después de 180 días. Nunca los compartimos."
  Font: JetBrains Mono 10px, color #6B8A6A, con ícono ShieldCheck verde.
- Botón primario "⟶ crear cuenta" / spinner + "creando cuenta…".
- Link "¿ya tienes cuenta? entra →" — "entra" en #F59E0B.

TOKENS + RESPONSIVE + TONO: idénticos a Login (Prompt 1).
Font: Pacifico (wordmark) + Space Grotesk (cuerpo) + JetBrains Mono (labels).
Dark-only. Hex-grid + scanlines en el fondo heredados del body global.
```

---

### Prompt 3 — Dashboard / Home (`/`)

```
Diseña la pantalla principal (post-login) de BioShield AI.

PANTALLA: Dashboard
ROUTE: / (autenticado)

PROPÓSITO: landing post-login. Tres acciones visibles: escanear producto,
subir biomarcadores, ver historial.

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
```

---

### Prompt 4 — Scanner (`/scan`)

```
Diseña la pantalla de escaneo de BioShield AI.

PANTALLA: Scanner
ROUTE: /scan

DOS MODOS EN LA MISMA PANTALLA (con Tabs):
  TAB 1: "Código de barras" (cámara con overlay de guía rectangular).
  TAB 2: "Foto de etiqueta" (captura frontal/trasera de la cámara o upload).

DATA FLOW:
- Barcode mode:
  - Librería: @zxing/browser lee código.
  - Al detectar: POST /scan/barcode { barcode: "8-14 dígitos" }
  - Response: ScanResponse (ver Prompt 5 para shape) o 404 si no se encontró
    en Open Food Facts → fallback "Intenta con /scan/photo".
- Photo mode:
  - Input file o captura de cámara.
  - Valida <10 MB.
  - Convierte a base64.
  - POST /scan/photo { image_base64: string }
  - Response: ScanResponse.

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

COMPONENTES:
- Header con botón back a Dashboard.
- Tabs horizontales (shadcn Tabs).
- Contenido tab 1: video preview 4:3 + overlay + input manual debajo "O ingresar código".
- Contenido tab 2: dropzone drag-and-drop + botón "Tomar foto" (mobile).
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
- Botones: bs-card + bs-glow-green.
- Font mono: JetBrains Mono para textos de estado y labels.

RESPONSIVE:
- Mobile: video full-width, controles grandes (botones 44px mín).
- Desktop: video max-width 640px centrado.

TONO: instructivo pero no paternalista. Mensajes cortos. Errores con
opción de recuperación, nunca callejón sin salida.
```

---

### Prompt 5 — Resultado de Scan (`/scan/[id]`)

**Esta es LA pantalla crítica del producto.** Merece el prompt más denso.

```
Diseña la pantalla de resultado de un escaneo en BioShield AI. Esta es la
pantalla CENTRAL del producto — donde el usuario entiende si un alimento es
seguro para su perfil de salud.

PANTALLA: Resultado de Scan
ROUTE: /scan/[id]

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

3. ALERTAS PERSONALIZADAS (solo si ORANGE):
   - Card destacada con borde naranja.
   - "Tu LDL está en 150 mg/dL y este producto contiene grasas trans."
   - Data source: el backend las computa en analysis.py con BIOMARKER_RULES.
   - En la v1 puede ser un array de strings; diseña para expansion futura.

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
```

---

### Prompt 6 — Biosync Upload (`/biosync`)

```
Diseña la pantalla de subida de biomarcadores (panel de sangre) en BioShield AI.

PANTALLA: Biosync
ROUTE: /biosync

CONTEXTO: el usuario sube resultados de laboratorio para que el análisis
de productos considere su perfil personal (ej: si tiene LDL alto, alerta
de grasas trans en productos escaneados).

DATA SHAPE (POST /biosync/upload):
{ data: { <key>: <value>, ... } }
Ejemplo: { data: { "ldl": 150, "hdl": 45, "glucose": 110, "triglycerides": 180,
                    "sodium": 3500, "uric_acid": 7.2 } }
El backend encripta con AES-256 y guarda con TTL de 180 días.

RESPONSE: BiomarkerStatusResponse
{ id, uploaded_at, expires_at, has_data: true }

DOS MODOS DE INGRESO (Tabs):
  TAB 1: "Manual" — formulario con campos tipados para los 5 biomarcadores
         con reglas conocidas del backend (analysis.py):
           - LDL (mg/dL)          rango normal: <100
           - HDL (mg/dL)          rango normal: >40
           - Glucose (mg/dL)      rango normal: 70-99
           - Triglycerides (mg/dL) rango normal: <150
           - Sodium (mg/día)      rango referencial: <2300
           - Uric acid (mg/dL)    rango normal: <7
         Cada campo con input number + unidad + tooltip con rango normal.
         Opción "Agregar otro biomarcador" (key-value genérico).
  TAB 2: "CSV" — dropzone que acepta .csv con headers estándar.
         Preview de primeras 5 filas después del upload.
         Botón "Procesar y subir".

ESTADOS GLOBALES (arriba de los tabs):
- Si GET /biosync/status devuelve has_data=true:
  - Banner ámbar: "Ya tienes biomarcadores activos. Expiran el DD/MM/YYYY.
    Subir nuevos los reemplaza."
  - Botón "Eliminar actuales" (DELETE /biosync/data, con confirmación modal).
- Si 404: banner info: "No tienes biomarcadores aún."

ESTADOS DE SUBIDA:
- Idle, Validating (rangos raros → warning inline no bloqueante),
  Uploading (progress bar), Success (toast + redirect a Dashboard),
  Error 401/422/red.

SECCIÓN DE PRIVACIDAD (sticky abajo en mobile, sidebar en desktop):
- Card con icono ShieldCheck y bullets:
  - "Encriptados con AES-256 antes de guardarse."
  - "Se borran automáticamente después de 180 días."
  - "Nunca se comparten ni se usan para entrenar modelos."
  - "Puedes eliminarlos en cualquier momento."

AVATAR BIOSYNC:
- Upload exitoso: success.png (80×80) en el toast/confirmación.
- Sin biomarcadores (empty state): welcome.png (100×100) con CTA de subir.

TOKENS (dark-only):
- Background: #080C07 con hex-grid + scanlines heredados.
- Tabs: shadcn, borde activo #4ADE80.
- Campos numéricos: mismo estilo que login (border rgba(74,222,128,.15),
  focus #4ADE80, label JetBrains Mono UPPERCASE 10px, color #6B8A6A).
- Banner has_data=true: border #F59E0B, bg rgba(245,158,11,.08), text #F59E0B.
- Dropzone CSV: border dashed rgba(74,222,128,0.3).
- Privacy card: bg rgba(74,222,128,.05), border rgba(74,222,128,.15),
  icono ShieldCheck #4ADE80, texto #6B8A6A.
- Botón primario: bs-glow-green, JetBrains Mono.
- Font sans: Space Grotesk. Font mono: JetBrains Mono.

RESPONSIVE:
- Mobile: tabs full-width, privacy card colapsada al fondo.
- Desktop ≥1024px: layout 2 columnas — formulario 2/3, privacy card 1/3 sticky.

TONO: tranquilizador. El usuario está compartiendo datos médicos sensibles —
la UI proyecta competencia y respeto sin ser agresivamente "corporativa".
La estética biotech (glows verdes, JetBrains Mono) refuerza que los datos
están en manos de tecnología seria.
```

---

### Prompt 7 — Historial de Scans (`/history`)

```
Diseña la pantalla de historial de escaneos de BioShield AI.

PANTALLA: Historial
ROUTE: /history

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
```

---

### Prompt 8 — Error / Empty / Loading globales

```
Diseña los 3 estados globales compartidos de BioShield AI:

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
- Sesión expirada: main.png (100×100, sin animate-wobble) en el dialog.
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
```

---

## Fase D — Implementación de cada item 7.1-7.6

### 7.1 · App Router + Tailwind + TanStack Query + Zustand

**Archivos:**
- `frontend/app/layout.tsx` — `<QueryClientProvider>` + fuentes (Pacifico/SpaceGrotesk/JetBrains). ✅ IMPLEMENTADO
- `frontend/app/globals.css` — tokens dark-only + hex-grid + semáforo ajustado. ✅ IMPLEMENTADO
- `frontend/lib/stores/auth.ts` — Zustand store con `user`, `setUser`, `logout`.
- `frontend/lib/api/client.ts` — fetcher con refresh automático (descrito en A.2).

**Checks de éxito:**
- `pnpm dev` arranca en :3000.
- Dark-only forzado: `<html class="dark">` — no hay ThemeToggle (eliminado del plan).
- TanStack Query devtools visible en dev.
- Fondo con hex-grid + scanlines visible en cualquier ruta.

**Nota sobre la desviación del doc:** el review §7 dice "zustand/SWR". Cambiamos SWR → TanStack Query porque tiene mejor DX para mutations, optimistic updates, y el cache por barcode (item 7.6) es trivial con `queryKey: ["scan", barcode]`. Zustand se queda para client state (auth).

### 7.2 · Auth UI consumiendo JWT HTTP-only

**Archivos:**
- `frontend/app/(auth)/login/page.tsx` — referencia visual: Prompt 1.
- `frontend/app/(auth)/register/page.tsx` — referencia visual: Prompt 2.
- `frontend/lib/api/auth.ts` — `login`, `register`, `logout`, `refresh`.
- `frontend/app/(app)/layout.tsx` — middleware guard: si `GET /biosync/status` responde 401 → redirect a `/login`.
- `frontend/middleware.ts` (Next.js) — chequea cookie presence para SSR routes.

**Checks de éxito:**
- Registro → auto-login → dashboard.
- 401 en cualquier request → reintento con `/auth/refresh` → si ok, sigue; si no, redirect login.
- Logout limpia cookies backend-side + Zustand store.

### 7.3 · Scanner UI

**Archivos:**
- `frontend/app/(app)/scan/page.tsx` — referencia visual: Prompt 4.
- `frontend/components/scanner/BarcodeScanner.tsx` — wrapper de `@zxing/browser`.
- `frontend/components/scanner/PhotoCapture.tsx` — input file + preview + base64 encoding.
- `frontend/lib/api/scan.ts` — `scanBarcode(barcode)` + `scanPhoto(base64)`.

**Checks de éxito:**
- Barcode real (Nutella 3017620422003) → navega a `/scan/[id]` con semaphore="YELLOW".
- Foto de etiqueta MX (usar `backend/test_images/*.jpeg` como fixtures) → pipeline completo.
- 404 en barcode muestra modal que cambia a photo tab.
- Permiso cámara denegado → fallback a input manual sin romper.

### 7.4 · Semáforo visual con detalles de conflict

**Archivos:**
- `frontend/app/(app)/scan/[id]/page.tsx` — referencia visual: Prompt 5.
- `frontend/components/semaphore/SemaphoreHero.tsx` — círculo + icono + label.
- `frontend/components/semaphore/SemaphoreBadge.tsx` — versión compacta para listas.
- `frontend/components/ingredients/IngredientCard.tsx` — accordion con conflicts.
- `frontend/components/ingredients/ConflictDetail.tsx` — severity + sources chips.

**Checks de éxito:**
- Los 5 colores se renderizan correctamente (forzar con fixtures en dev).
- Accordion expande y muestra CAS/E-number en mono + conflicts ordenados por severity.
- Alertas de biomarcadores aparecen solo si `semaphore === "ORANGE"`.
- Accesibilidad: navegar con teclado + screen reader (macOS VoiceOver) anuncia semáforo.

### 7.5 · Biosync UI

**Archivos:**
- `frontend/app/(app)/biosync/page.tsx` — referencia visual: Prompt 6.
- `frontend/components/biosync/BiomarkerForm.tsx` — form tipado con los 5 biomarcadores conocidos + "agregar otro".
- `frontend/components/biosync/BiomarkerCSVUpload.tsx` — dropzone + preview.
- `frontend/lib/api/biosync.ts` — `uploadBiomarkers(data)`, `getStatus()`, `deleteBiomarkers()`.

**Checks de éxito:**
- Upload manual de `{ ldl: 150, glucose: 110 }` → 201 → redirect.
- Status endpoint muestra expires_at correcto.
- Delete con modal de confirmación.
- Scan de producto con grasas trans post-upload → semaphore ORANGE.

### 7.6 · TanStack Query cache por barcode

**Implementación:**
- `queryKey: ["scan", "barcode", barcode]` con `staleTime: 5 * 60 * 1000` (5 min).
- El cache es por-usuario (React Query por tab/session); persistencia opcional con `@tanstack/query-async-storage-persister` + `localStorage` si queremos offline-friendly.

**Checks de éxito:**
- Escanear mismo barcode 2 veces en <5min → segunda llamada sirve de cache, sin request al backend (devtools lo confirma).
- Forzar refetch con botón "Actualizar" en la pantalla de resultado.

---

## Fase E — Handoff claude.ai/design → `/frontend`

### E.0 · Formato de entrega establecido (basado en el login ✅)

El login entregó el paquete completo. Este es el estándar para las 7 pantallas restantes:

```
docs/design/<pantalla>/
├── README.md              ← spec completo con CSS exacto por componente
├── design-tokens.json     ← tokens tipados ($schema community-group)
└── reference/
    └── BioShield <Pantalla>.html  ← prototipo interactivo React+Babel
```

Estructura del README.md esperado por pantalla:

```
# Handoff: BioShield AI — `/<ruta>`
Versión · Fecha · Diseñado en · Implementar en
─────────────────────────────────────
⚠️  Sobre los archivos de diseño
📁  Dónde colocar cada archivo en Next.js  ← rutas de componentes específicas
🎨  Tokens de marca (tabla resumen)
🖥️  Pantalla — Layout + fondo decorativo + card
    → specs de cada sección en CSS exacto
🍍  Avatar mascota (si aplica)
    → src, tamaño, animación, glow
    → nombre de archivo EXACTO del /public/avatars/
🔤  Wordmark (solo si aparece en la pantalla)
📋  Componentes — uno por sección, con props, CSS por estado
⚡  Estados de la UI — tabla trigger → comportamiento
🔌  Integración API — snippet con endpoint, método, body
📦  Assets incluidos (tabla)
✅  Checklist de implementación
```

---

### E.1 · Correcciones globales — divergencias login vs nuestro codebase

El handoff del login tuvo 6 puntos que difieren de nuestra implementación real.
Aplicar estas correcciones al pegar cada handoff en código:

| # | Lo que dijo el handoff | Lo correcto en este proyecto |
|---|---|---|
| 1 | Avatar names: `mascot-happy.png`, `mascot-error.png`, `mascot-loading.png` | Nuestros PNGs: `success.png`, `support.png`, `progress.png`, `welcome.png`, `profile.png` + semáforos `gray/blue/yellow/orange/red.png` |
| 2 | "JetBrains Mono no está en next/font" | Sí está. Ya cargada en `layout.tsx` como `--font-jetbrains-mono`. No usar `@import`. |
| 3 | `tokens/design-tokens.json` como destino de los tokens | Tokens ya están en `globals.css` + documentados en `docs/design/tokens.md`. Ignorar la sección "Tokens de diseño" de archivo y absorber solo los valores nuevos o diferenciales. |
| 4 | `hooks/useLoginForm.ts` — lógica en hook custom | Lógica va en `lib/api/auth.ts` (o `scan.ts`, `biosync.ts`). En componentes, usar TanStack Query mutations (`useMutation`), no hooks custom. |
| 5 | `router.push('/dashboard')` | Dashboard está en `/` (group `(app)/page.tsx`). Usar `router.push('/')`. |
| 6 | Nombres de tokens: `--green`, `--amber`, `--surface` | Nuestros tokens son `--brand-green`, `--brand-amber`, `bg-surface`. Mapear al usar. |

---

### E.2 · Proceso de handoff por pantalla

**Orden de implementación** (por valor entregado):
1. Register — desbloquea auth completo.
2. Scanner + Resultado — core del producto.
3. Biosync — activa diferenciación ORANGE.
4. Dashboard — tie-together.
5. Historial — pulido.
6. Error/Loading — estados globales.

**Proceso por cada pantalla:**
1. Diseñar en claude.ai/design con el prompt de Fase C (ya actualizado con tokens correctos).
2. Iterar (3-5 rondas típicamente). Si los tokens divergen de los del login, forzar corrección antes de cerrar.
3. Solicitar entrega del paquete completo: README + design-tokens.json + .html.
4. Guardar en `frontend/temp/<pantalla>/`.
5. Aplicar correcciones de E.1.
6. Implementar en `/frontend` con shadcn/ui + tipos de `lib/api/types.ts` + TanStack Query.
7. Smoke test manual de la pantalla antes de pasar a la siguiente.

---

### E.3 · Especificaciones por pantalla — qué debe cubrir cada handoff README

Lo que el login estableció como base. Lo que sigue son las **adiciones específicas** que cada pantalla necesita sobre ese template.

---

#### Pantalla 2 — Register (`/register`)

**Componentes que deben quedar especificados:**
- `PasswordStrengthBar` — barra bajo el campo de password con 3 estados:
  - corta (< 6 chars): `#F87171`, ancho 33%
  - media (6-9 chars): `#F59E0B`, ancho 66%
  - fuerte (≥ 10 chars + variedad): `#4ADE80`, ancho 100%
  - height 3px, border-radius 2px, transition width 0.3s
- `AuthField` — debe reutilizar el de login sin cambios.
- `PrivacyNote` — párrafo de privacidad (ShieldCheck + texto 2 líneas).
  CSS: JetBrains Mono 10px, `#6B8A6A`, borde-left 2px `rgba(74,222,128,.3)`, padding-left 10px.
- Checkbox: custom, no el del navegador. Border `rgba(74,222,128,.3)`, checked: `#4ADE80`.

**Estados adicionales al login:**
- `validating` — campo password con barra de fuerza actualizando en tiempo real.
- `409` — alerta `[ERROR_409] Email ya registrado.` (mismo estilo que 401).

**Avatar:** mismo `main.png` + wobble que login.

**Ruta de destino post-register:** `router.push('/')` (no `/dashboard`).

---

#### Pantalla 3 — Dashboard (`/`)

**Componentes que deben quedar especificados:**
- `Navbar` — altura 56px, fondo `#0D1310`, borde-bottom `rgba(74,222,128,.1)`.
  - Izquierda: wordmark compacto (sin tagline).
  - Derecha: `profile.png` (32×32, rounded-full) + nombre usuario + `<ChevronDown/>` → dropdown (Logout).
- `HeroCard` — bs-card + corner accents. CTA "⟶ escanear producto".
  - Icono: `Camera` o `Barcode` (alternar con Tabs?).
- `BiosyncStatusCard` — secondary card, sin corner accents.
  - Estado `has_data=true`: badge "biomarcadores activos", fecha expira en `#F59E0B` si < 30 días.
  - Estado `404`: CTA "subir panel de sangre".
- `RecentScanRow` — fila compacta: SemaphoreBadge (40×40) + nombre + fecha relativa + chevron.
- `SemaphoreBadge` (40px) — círculo con fondo `rgba(semaphore-color, 0.2)` + icono Lucide color sólido.

**Estados adicionales:**
- `empty` (sin historial): `welcome.png` (120×120) centrado + "Escanea tu primer producto".
- Skeletons: 3 variantes — card hero, card secondary, lista de filas.

**Avatar:** `welcome.png` en empty state. `profile.png` en navbar.

---

#### Pantalla 4 — Scanner (`/scan`)

**Componentes que deben quedar especificados:**
- `BarcodeScanner` — video element:
  - Contenedor: max-width 480px, aspect-ratio 4/3.
  - Overlay: `rgba(0,0,0,.5)` con recorte centrado transparent (la "ventana" del scanner).
  - Borde de la ventana: 2px `#4ADE80`, border-radius 8px.
  - Laser line: `div` absoluto, altura 2px, `background: linear-gradient(90deg, transparent, #4ADE80, transparent)`, `animation: scan-line 2s linear infinite` (ya en globals.css).
  - Flash en detección: background de la ventana cambia a `rgba(74,222,128,.2)`, 300ms, una vez.
- `PhotoCapture` — dropzone:
  - Borde: `2px dashed rgba(74,222,128,.3)`. Hover: `rgba(74,222,128,.6)`.
  - Fondo: `rgba(74,222,128,.03)`.
  - Icono: `Upload` o `ImagePlus` (Lucide), color `#6B8A6A`.
  - Mobile: botón adicional "Tomar foto" (input `capture="environment"`).
- `CameraPermissionCard` — bs-card compacto. Icono `Camera`, texto, CTA verde.
- `NotFoundModal` — dialog shadcn: mensaje + CTA que cambia al tab 2.
- `ManualBarcodeInput` — input regular de `AuthField` para fallback.

**Estados adicionales:**
- Loading foto: `progress.png` (100×100, animate-pulse-glow) centrado con texto "Analizando etiqueta con IA...".
- Permiso denegado: `support.png` (80×80) + fallback input manual.

---

#### Pantalla 5 — Resultado de Scan (`/scan/[id]`)

**Componentes que deben quedar especificados:**
- `SemaphoreHero` — la sección crítica:
  - Layout: flex row (gap-6) en desktop, columna en mobile.
  - Círculo: 120×120px, fondo `rgba(semaphore-color, 0.15)`, borde 2px `rgba(semaphore-color, 0.6)`, borde-radius 50%, `animate-pulse` sutil.
  - Icono Lucide en el centro: 40×40, color sólido del semáforo.
  - Avatar PNG lateral: 120×120, `animate-pulse-glow`, `alt=""` + `aria-hidden`.
  - El borde del card contenedor cambia según semáforo: `border-color: rgba(semaphore-color, 0.4)`.
- `IngredientAccordion` — cada ítem:
  - Header (collapsed): nombre + badge status (Approved/Banned/Restricted/Under Review) + barra confidence + badge "N conflictos" si aplica.
  - Expanded: CAS number y E-number en `font-mono`, lista de conflictos.
  - Borde-bottom entre ítems: `rgba(74,222,128,.08)`. Hover fondo: `rgba(74,222,128,.04)`.
- `ConflictRow` — severity badge + summary + sources chips.
  - HIGH: `rgba(248,113,113,.15)` bg, border `#F87171`.
  - MEDIUM: `rgba(251,146,60,.15)` bg, border `#FB923C`.
  - LOW: `rgba(250,204,21,.15)` bg, border `#FACC15`.
- `BiomarkerAlert` — card con borde `#FB923C`, solo visible si `semaphore === "ORANGE"`.

**Estados adicionales:**
- Skeleton hero + 3 skeleton acordeones (con shimmer verde, no gris).

**Avatar:** PNG del semáforo correspondiente al lado del `SemaphoreHero`.
Mapeo: `gray.png` / `blue.png` / `yellow.png` / `orange.png` / `red.png`.

---

#### Pantalla 6 — Biosync (`/biosync`)

**Componentes que deben quedar especificados:**
- `BiomarkerField` — campo numérico + unidad + tooltip:
  - Layout: input (flex-1) + unidad text (`#6B8A6A`, JetBrains Mono, padding 0 8px) en fila.
  - Tooltip icono `Info` (Lucide, 12px) con popup: rango normal del marcador.
  - Validación inline: si valor fuera de rango, warning ámbar NO bloqueante.
- `AddBiomarkerRow` — par key-value genérico. Botón `+` con borde `rgba(74,222,128,.3)`.
- `CSVDropzone` — mismo estilo que `PhotoCapture` de scanner.
- `CSVPreviewTable` — primeras 5 filas del CSV. Fondo `#0D1310`, headers JetBrains Mono.
- `BiomarkerBanner` — dos variantes:
  - `has_data`: `rgba(245,158,11,.08)` bg, border ámbar, botón "Eliminar" secundario.
  - `empty`: `rgba(74,222,128,.05)` bg, border verde, texto neutro.
- `PrivacyCard` — bs-card sin corner accents. ShieldCheck verde. 4 bullets JetBrains Mono.
- `DeleteConfirmModal` — dialog shadcn con confirmación destructiva (botón rojo).

**Avatar:** `success.png` (80×80) en toast de confirmación post-upload.

---

#### Pantalla 7 — Historial (`/history`)

**Componentes que deben quedar especificados:**
- `HistoryRow` — fila compacta:
  - `SemaphoreBadge` (40×40) a la izquierda.
  - Centro: nombre producto (Space Grotesk, 14px) + barcode (JetBrains Mono, 11px, `#6B8A6A`).
  - Derecha: fecha relativa (Space Grotesk 12px) + chip source + `ChevronRight`.
  - Borde-bottom: `rgba(74,222,128,.08)`. Hover: `rgba(74,222,128,.04)`.
- `DayGroupHeader` — separador de sección:
  - Texto: "Hoy" / "Ayer" / fecha. JetBrains Mono UPPERCASE 10px, `#6B8A6A`, tracking 0.1em.
  - Sin línea decorativa extra — el contraste del fondo es suficiente.
- `FilterTabs` — shadcn Tabs, cada label con badge count:
  - Badge: `rgba(semaphore-color, 0.2)` bg, color sólido, font-mono 10px.
  - Tab "Todos": badge `rgba(74,222,128,.2)`.
- `SearchInput` — mismo estilo que `AuthField` pero sin label UPPERCASE ni icono izquierdo.
  Icono: `Search` (Lucide, `#6B8A6A`).

**NO usar avatar PNG en las filas** — solo `SemaphoreBadge` (círculo + icono). Los PNGs son para heroes, no para listas densas.

**Avatar:** `welcome.png` (120×120) en empty state sin scans.

---

#### Pantalla 8 — Error / Empty / Loading

**Componentes que deben quedar especificados:**
- `ErrorPage` (500 / red) — full-page, centrado:
  - `support.png` (120×120) arriba, sin wobble ni glow (estático).
  - Título "algo salió mal." — Space Grotesk 2xl, `#DCF0DC`.
  - Subtítulo — JetBrains Mono 13px, `#6B8A6A`.
  - Dos botones: primario "reintentar" (bs-glow-green) + secundario "ir al inicio" (borde `rgba(74,222,128,.3)`).
- `SessionExpiredDialog` — dialog shadcn:
  - `main.png` (80×80, estático, sin wobble) centrado en el header del dialog.
  - Título, texto, botón "entrar de nuevo".
  - Fondo: bs-card. Borde: `rgba(74,222,128,.18)`.
- `SkeletonCard` / `SkeletonRow` / `SkeletonHero` — 3 variantes:
  - Color base: `rgba(74,222,128,.06)`.
  - Shimmer: `background: linear-gradient(90deg, transparent, rgba(74,222,128,.1), transparent)` con `animation: shimmer 1.5s infinite`.
  - NO grises — el shimmer mantiene el mood verde del sistema.

**Keyframe shimmer** (agregar a globals.css en Fase D):
```css
@keyframes shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position:  200% 0; }
}
```

---

## Archivos críticos — resumen

**Backend (ya existen, solo lectura para mirror de tipos):**
- `backend/app/schemas/models.py` — source of truth para `frontend/lib/api/types.ts`.
- `backend/app/routers/{auth,scan,biosync}.py` — contracts.
- `backend/app/services/analysis.py` — BIOMARKER_RULES que alimentan los hints del form de biosync.
- `backend/app/main.py` línea 24-30 — CORS (verificar `ALLOWED_ORIGINS`).

**Frontend (nuevos):**
- `frontend/package.json`, `frontend/next.config.ts`, `frontend/tailwind.config.ts`.
- `frontend/app/layout.tsx`, `frontend/app/globals.css`.
- `frontend/lib/api/{client,auth,scan,biosync,types}.ts`.
- `frontend/lib/stores/auth.ts`.
- 8 archivos de página en `frontend/app/(auth)/**` y `frontend/app/(app)/**`.
- 15-20 componentes en `frontend/components/**`.

**Docs nuevos:**
- `docs/design/README.md` — índice de pantallas con links a sesiones de Claude Design + screenshots.
- `docs/design/<pantalla>.png` × 8.
- `docs/reviews/18-04.md` — actualizar §13 con cierre de Fase 7.

**DevOps:**
- `docker-compose.yml` — agregar servicio `frontend` (Fase A.4).
- `.github/workflows/ci.yml` — agregar job `frontend-build` (pnpm install + build + lint + typecheck).

---

## Verificación end-to-end

Después de implementar, validar con estos casos en navegador real (Chrome + Safari mobile) apuntando a `docker compose up`:

1. **Happy path barcode:**
   - Register → Login → `/scan` → barcode tab → escanear `3017620422003` (Nutella) → `/scan/[id]` muestra semaphore YELLOW con ingredientes + conflicts.
2. **Happy path photo:**
   - `/scan` → photo tab → subir `backend/test_images/1.jpeg` → semaphore computado → detalle correcto.
3. **Orange biomarker match:**
   - `/biosync` → manual → `{ ldl: 150 }` → upload OK.
   - `/scan/barcode` de un producto con grasas trans → semaphore ORANGE con alerta "Tu LDL está en 150 y este producto contiene grasas trans".
4. **Cache SWR/TanStack:**
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

## Estimación de esfuerzo

| Fase | Esfuerzo | Dependencias |
|---|---|---|
| A — Setup monorepo | 3-4h | — |
| B — Design tokens | 1h | Acuerdo sobre paleta |
| C — Diseñar 8 pantallas en claude.ai/design | 6-10h | Tokens de B listos |
| D — Implementar 7.1-7.6 | 3-4 días | Fase C completa; backend levantado |
| E — Handoff + integración | Embebido en D | — |
| Verification E2E | 4-6h | Todo anterior |
| **Total** | **~5-7 días** | Backend ya listo |

Alberto puede paralelizar Fase C (mientras diseña en Claude Design) con Fase A-B (setup del repo) para comprimir a ~4 días.

---

## Riesgos y mitigaciones

1. **Drift entre tipos FE y schemas BE.**
   Mitigación: generar tipos con `openapi-typescript` contra `/openapi.json` en CI. Bloqueante si falla.

2. **Permisos de cámara en iOS Safari.**
   Mitigación: Fallback input manual de barcode siempre disponible; PhotoCapture acepta file upload sin cámara.

3. **Free tier de Gemini agotado en dev** (§9.3 del review).
   Mitigación: mockear `POST /scan/photo` con fixture de ScanResponse en desarrollo FE; scan real contra staging con tier pagado.

4. **Claude.ai/design no exporta React con shadcn directamente.**
   Mitigación: el código generado es referencia visual; la implementación en `/frontend` usa shadcn explícitamente. No intentar `npm install` del output de Claude Design crudo.

5. **Cookies cross-origin en producción.**
   Mitigación: mismo dominio FE+BE con subdominio (`app.bioshield.ai` + `api.bioshield.ai`) y `SameSite=Lax` (ya configurado en backend). Si despliegue inicial es Vercel (FE) + Render (BE) en dominios distintos, requiere `SameSite=None; Secure`. Verificar en staging antes de prod.
