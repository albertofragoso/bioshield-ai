# BioShield AI — Frontend

## Qué es

Frontend Next.js 16 (App Router) que consume la API REST del backend FastAPI.
Permite al usuario escanear productos (cámara barcode + foto etiqueta), visualizar
el semáforo nutricional con detalle de conflictos por ingrediente, y gestionar sus
biomarcadores de sangre para alertas personalizadas.

## Stack

> Stack completo y convenciones de negocio en `.claude/CLAUDE.md` (raíz del repo).

Adiciones específicas del frontend:

- **Framework:** Next.js 16 con App Router y TypeScript strict
- **Estilos:** Tailwind CSS v4 + shadcn/ui (Radix primitives)
- **Server state:** TanStack Query v5 (cache, mutations, retry)
- **Client state:** Zustand v5 (auth: user, isAuthenticated)
- **Validación:** Zod v4 (schemas que espejean `backend/app/schemas/models.py`)
- **Scanner barcode:** @zxing/browser + @zxing/library
- **Auth:** JWT via HTTP-only cookies — el frontend NUNCA lee los tokens directamente

## Convenciones

- **Cliente API:** todo fetch pasa por `lib/api/client.ts`. Nunca llamar `fetch()` directo en componentes.
- **Tipos:** `lib/api/types.ts` es el espejo de los schemas del backend. Si el backend cambia un schema, actualizar aquí también.
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
- **Next.js App Router:** https://nextjs.org/docs/app
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
