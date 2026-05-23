# BioShield AI — Marketing Landing Page

**Fecha:** 2026-05-22  
**Estado:** IMPLEMENTADO — branch `feature/marketing-landing` (2026-05-23)  
**Audiencia primaria:** MX health-conscious mainstream (25-45, urbano, usa Chopo/Salud Digna)  
**Audiencia secundaria:** Dev/founder community MX-LatAm (LinkedIn, Product Hunt)

---

## Contexto

BioShield AI está en producción técnica con todas las features core operativas:
- Pipeline LangGraph 8-node con SSE streaming
- Scan por barcode + foto (Gemini 2.5 Flash visión)
- Biomarker matching con AES-256, TTL 180d
- Alternativas hybrid SQL + ChromaDB
- Sharing por link público (7 días)
- Hardening completo (rate limiting, token budget atómico, JSON logs, errores unificados)

**Problema:** `/` está ocupada por el dashboard autenticado. No existe landing pública. Sin ella, el proyecto no tiene presencia pública ni mecanismo de adquisición.

**Outcome:** Landing pública en `/` que captura emails de waitlist de la audiencia primaria y hace showcase técnico para la secundaria.

---

## Decisiones de diseño

| Decisión | Elección | Razón |
|---|---|---|
| Objetivo primario | Waitlist + showcase técnico | Sin Stripe; sin pricing visible |
| Audiencia única | MX health-conscious mainstream | Evita tono dual que filtra al usuario común |
| Tono visual | Biotech-hacker SUAVIZADO | Glows/scanlines como soporte; JetBrains Mono solo en data badges |
| Demo pipeline | Replay SSE trace REAL serializado | Evita churn post-beta por divergencia demo vs producto |
| Pricing en landing | Cero | Roadmap futuro, NO en UI |
| Ruta `/` | Route group `(marketing)`, 100% static | Middleware no toca `/`; p99 TTFB < 200ms |

---

## Arquitectura de rutas

```
frontend/app/
├── (marketing)/
│   ├── layout.tsx          ← header minimal (logo + "Entrar")
│   └── page.tsx            ← landing 9 secciones, force-static
├── (auth)/                 ← sin cambios
├── (app)/
│   ├── home/page.tsx       ← MOVIDO desde (app)/page.tsx
│   └── ...                 ← sin cambios
└── proxy.ts                ← matcher restrictivo (Next.js 16 usa proxy.ts, NO middleware.ts)
```

**⚠️ Gotcha Next.js 16:** En Next.js 16, `middleware.ts` fue renombrado a `proxy.ts` con función `proxy()`. Crear `middleware.ts` cuando ya existe `proxy.ts` causa error de arranque. Siempre consultar Context7 `/vercel/next.js` antes de implementar patrones de routing.

**proxy.ts matcher** — no toca `/`, `/api/waitlist`, `assets`, `avatars`, ni `/demo/` (fixtures del pipeline animado):

```ts
export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|api/waitlist|assets|avatars|demo|$).*)'
  ]
}
```

⚠️ **Gotcha demo fixtures:** El path `/demo/*.json` debe estar excluido del proxy. Si no, usuarios no autenticados reciben redirect 302 a `/login` al intentar cargar los fixtures del `PipelineLoopAnim`, dejando el demo atascado en "Cargando demo..." sin error visible.

Usuario autenticado en `/` ve un banner "Ir a tu dashboard" (1 click). No hay redirect server-side para preservar TTFB.

La landing usa `export const dynamic = 'force-static'`.

---

## Secciones — estructura y copy

### 1. Hero — 100vh

**Componentes:**
- `HomeOrbSection` adaptado (sin Link, mascota `main.png` prominente 126×126)
- `PipelineLoopAnim` — replay SSE trace real (ver sección Demo)
- `HeroWaitlistCTA` — form inline
- `RegulatoryBanner` — sticky bottom

**Copy:**
```
Eyebrow:   BioShield AI · Nutrición inteligente
H1:        Lo que comes, en términos de TU sangre.
Sub:       Escanea cualquier producto. Descubrí qué aditivos contiene
           y si son compatibles con tus análisis de laboratorio.
Badge mono: hack your nutrition · protect your biology
CTA 1:     Quiero acceso anticipado
CTA 2:     Ver demo ↓
```

### 2. El momento revelador — ~80vh

**Componentes:**
- `RevealMomentStory` (scroll-triggered, CSS + Intersection Observer)
- `SemaphoreBadge` (variants orange/red)
- `AvatarGlow`

**Copy:**
```
H2:   Lo que tu etiqueta no te dice.
Body: Carragenina (E407). Tu lab muestra LDL elevado.
      BioShield te muestra la correlación reportada en estudios públicos
      — para que decidas con tu médico.
```

Visual: scan de un yogurt + biomarker overlay (sin claim de outcome).

### 3. Cómo te ayuda — ~70vh

**Componentes:**
- `HowItHelpsGraph` (SVG inline animado, 5 pasos, hex-grid de fondo)

**Copy:**
```
H2:    Cómo te ayuda BioShield
Pasos: Escaneás → Reconocemos ingredientes → Cruzamos con FDA/EFSA/Codex
       → Comparamos con tu laboratorio → Te mostramos correlaciones
```

Nota visible en paso 5: "No es diagnóstico. Son correlaciones informativas."

### 4. Por qué es diferente — ~80vh

**Componentes:**
- `BiomarkerSplitPanel` (producto izq / sangre der, aesthetic de `AlternativesHeroPanel`)

**Copy:**
```
H2: Otras apps te dicen calorías. BioShield contextualiza con TU sangre.
```

Tabla comparativa simple (sin nombrar competidores por nombre).

### 5. Fuentes regulatorias — ~40vh

**Componentes:**
- `RegulatoryTrust` strip

**Copy:**
```
Información basada en FDA EAFUS · EFSA OpenFoodTox · Codex Alimentarius
[N] ingredientes indexados
```

**IMPORTANTE:** [N] = número REAL obtenido de `SELECT COUNT(*) FROM ingredients` en ChromaDB antes de hacer deploy. No hardcodear sin verificar.

### 6. Waitlist CTA — ~70vh

**Componentes:**
- `WaitlistHero` (form + counter en rangos + Turnstile invisible + consent checkbox)

**Copy:**
```
H2:           Sé de los primeros en probarlo.
Form fields:  Email (requerido) · Nombre (opcional)
Select:       ¿Para qué lo usarías? [Salud personal / Interés técnico / Otro]
Checkbox:     Acepto recibir invitación al beta Q2 2026 (LFPDPPP México)
CTA:          Unirme a la lista
Privacy note: Cero spam. Datos cifrados AES-256. Puedes pedir borrado cuando quieras.
Counter:      +[rango] personas en la lista  ← rangos hasta >500 reales
```

Counter en rangos hasta tener >500 signups reales:
- 0–49 → "+40 personas" (número fijo)
- 50–99 → "+80 personas"
- 100–199 → "+100 personas"
- 200–499 → "+200 personas"
- 500+ → número real

### 7. FAQ — auto height

**Componentes:**
- `MarketingFAQ` (shadcn Accordion, 10 items)

| Pregunta | Respuesta |
|---|---|
| ¿BioShield diagnostica enfermedades? | No. Herramienta educativa. Las decisiones de salud son entre vos y tu médico. |
| ¿Está avalada por COFEPRIS o FDA? | No. Información extraída de bases públicas regulatorias. |
| ¿Qué hace con mis biomarcadores? | Cifrados AES-256, expiran en 180 días, borrado on-demand. |
| ¿Cuánto va a costar? | Core gratis siempre. Tier Pro en evaluación. |
| ¿Cuándo lanza? | Beta limitada Q2 2026. |
| ¿En qué países? | México primero. LatAm después. |
| ¿Funciona sin conexión? | No por ahora. |
| ¿Puedo contribuir productos? | Sí, vía Open Food Facts integrado. |
| ¿Hay app móvil? | PWA optimizada mobile-first. |
| ¿Cómo borro mis datos? | Botón "Borrar todo" en biosync + `privacy@bioshield.mx`. |

### 8. Stack técnico — ~50vh

**Componentes:**
- `StackStrip` (minimalista, para audiencia tier-2)

**Copy:**
```
Construido con tecnología abierta para que puedas auditar cómo funciona.
```

Logos: Next.js · FastAPI · LangGraph · Gemini · ChromaDB · [enlace GitHub]

Posición: después del waitlist CTA, no antes. Evita filtrar a mainstream antes de capturar el email.

### 9. Footer — auto height

**Componentes:**
- `MarketingFooter`
- `RegulatoryBanner` (repetido)

**Links:** Privacy · Términos · GitHub · `press@bioshield.mx` · Contacto  
**Copyright:** `© 2026 BioShield AI · Hecho en MX`

---

## Compliance regulatorio (hard-gate)

### Blocklist de copy — prohibido en cualquier texto público

```
detectamos · riesgo cardiovascular · diagnóstico · biomarker matching
analizamos tu salud · predicción de · previene · cura · tratamiento
```

### Permitido

```
explora correlaciones nutricionales con tus valores de laboratorio
uso educativo · no sustituye consulta médica
herramienta informativa · información de bases públicas regulatorias
```

### Componentes obligatorios de compliance

- `RegulatoryBanner` — sticky bottom en TODAS las páginas `(marketing)`:  
  `Herramienta educativa. No sustituye consulta médica. No avalada por COFEPRIS/FDA.`
- `DemoDisclaimerModal` — click-through antes de abrir el demo, checkbox obligatorio:  
  `Entiendo que esto no es diagnóstico médico`
- Watermark en demo loop:  
  `Simulación con datos reales pre-grabados`

---

## Demo pipeline — replay de SSE trace real

La animación del pipeline **no es inventada**. Funciona en dos pasos:

**Paso 1 — Generar fixtures** (`backend/scripts/record-demo-trace.py`):
1. Corre scan real contra `POST /scan/barcode` con 3 productos (yogurt, granola, agua saborizada)
2. Captura todos los eventos SSE con timing real
3. Serializa a `frontend/public/demo/scan-trace-{barcode}.json`

Schema del fixture:
```json
{
  "barcode": "7501234567890",
  "product_name": "Yogurt Danone Natural",
  "events": [
    {"t_ms": 0,    "type": "init",        "data": {...}},
    {"t_ms": 1200, "type": "ingredients", "data": {...}},
    {"t_ms": 8400, "type": "done",        "data": {...}}
  ]
}
```

**Paso 2 — Componente `PipelineLoopAnim`**:
- Consume el mismo `useScanStore` (Zustand) de producción
- Replayea con timing real (si el pipeline tarda 8s, el demo tarda 8s — sin acelerar)
- Rota entre 3 productos en loop infinito
- Watermark siempre visible

**Snapshot test** (`tests/specs/scan/sse-contract.spec.ts`):
- Compara schema de los fixtures vs schema actual del backend SSE
- Falla si divergen → obliga a regenerar fixtures antes de release

---

## Waitlist backend

### Modelo `WaitlistSignup`

```python
class WaitlistSignup(Base):
    id: UUID                    # PK
    email: str                  # almacenado lowercase
    name: str | None
    source: str | None          # utm_source
    signup_intent: str | None   # "salud_personal" | "interes_tecnico" | "otro"
    consent_text: str           # snapshot del checkbox en el momento del signup
    expires_at: datetime        # NOW() + 365 days
    created_at: datetime
    contacted_at: datetime | None
```

Índice para idempotencia:
```sql
CREATE UNIQUE INDEX waitlist_signups_email_lower_idx
ON waitlist_signups (LOWER(email));
```

### Endpoints

**`POST /waitlist`** — público, rate limit 5/min por IP, Turnstile server-side

- Body: `{email, name?, source?, signup_intent?, consent: bool, turnstile_token: str}`
- 422 si `consent: false`, email inválido, o Turnstile falla
- `INSERT ... ON CONFLICT (LOWER(email)) DO NOTHING RETURNING id`
- 201 + `{position, total}` si es nuevo
- 409 + `{message: "ya estás en la lista"}` si conflict

**`GET /waitlist/count`** — público, cached 60s

- `SELECT COUNT(DISTINCT LOWER(email)) FROM waitlist_signups WHERE expires_at > NOW()`
- Frontend convierte a rangos

### Cron cleanup (LFPDPPP)

```python
# scripts/expire_waitlist.py — reusa patrón de expire_biomarkers.py
DELETE FROM waitlist_signups
WHERE expires_at < NOW() AND contacted_at IS NULL;
```

---

## Distribución — canales pre-comprometidos

Ningún launch sin owner + CAC + deadline asignados:

| # | Canal | Owner | CAC est. | Deadline |
|---|---|---|---|---|
| 1 | 5 nutriólogas micro-influencer CDMX (5-20K followers) | TBD founder | ~$30 USD/signup | Outreach T-21, 2 confirmadas T-7 |
| 2 | IG/TikTok orgánico `@bioshield.mx` | TBD founder+designer | $0 | 5 reels pre-launch + calendario 30d |
| 3 | LinkedIn founder post + Product Hunt | TBD founder | $0-50 | PH T-7 con hunters, LinkedIn day-of |

**Métrica de éxito 90 días post-launch:**
- ≥40% de signups → `signup_intent: "salud_personal"` (audiencia primaria capturada)
- ≤30% → `signup_intent: "interes_tecnico"`
- Si >70% técnico a 2 semanas → kill LinkedIn/PH, double-down en nutriólogas

---

## SEO y metadata

**`frontend/app/layout.tsx`** — actualizar:
```ts
title: { default: "BioShield AI", template: "%s · BioShield AI" }
description: "Escanea productos y descubre su compatibilidad con tus análisis de laboratorio."
keywords: ["nutrición", "biomarcadores", "aditivos", "salud", "México"]
openGraph: { images: ["/api/og"] }
twitter: { card: "summary_large_image" }
```

**`frontend/app/api/og/route.tsx`** — OG image dinámica con `@vercel/og`  
**`frontend/app/sitemap.ts`** — incluye `/`, `/privacy`, `/terms`  
**`frontend/app/robots.ts`** — permite indexación de `(marketing)`, bloquea `(app)` y `(auth)`

---

## Archivos críticos

### Nuevos

| Path | Propósito |
|---|---|
| `frontend/app/(marketing)/layout.tsx` | Header marketing minimal |
| `frontend/app/(marketing)/page.tsx` | Landing 9 secciones, force-static |
| `frontend/middleware.ts` | Matcher restrictivo |
| `frontend/components/marketing/PipelineLoopAnim.tsx` | Replay SSE trace |
| `frontend/components/marketing/HeroWaitlistCTA.tsx` | CTA inline en hero |
| `frontend/components/marketing/RegulatoryBanner.tsx` | Sticky bottom compliance |
| `frontend/components/marketing/DemoDisclaimerModal.tsx` | Click-through pre-demo |
| `frontend/components/marketing/RevealMomentStory.tsx` | Sección 2 storytelling |
| `frontend/components/marketing/HowItHelpsGraph.tsx` | SVG animado 5 pasos |
| `frontend/components/marketing/BiomarkerSplitPanel.tsx` | Split producto/sangre |
| `frontend/components/marketing/RegulatoryTrust.tsx` | Strip fuentes + counter |
| `frontend/components/marketing/WaitlistHero.tsx` | Form con Turnstile + consent |
| `frontend/components/marketing/MarketingFAQ.tsx` | Accordion 10 items |
| `frontend/components/marketing/StackStrip.tsx` | Stack tech tier-2 |
| `frontend/components/marketing/MarketingFooter.tsx` | Footer legal |
| `frontend/public/demo/scan-trace-{barcode}.json` × 3 | Fixtures SSE reales |
| `frontend/app/api/og/route.tsx` | OG image dinámica |
| `frontend/app/sitemap.ts` | Sitemap.xml |
| `frontend/app/robots.ts` | Robots.txt |
| `backend/app/routers/waitlist.py` | POST /waitlist + GET /waitlist/count |
| `backend/alembic/versions/{rev}_add_waitlist_signups.py` | Migración + UNIQUE index |
| `backend/scripts/record-demo-trace.py` | Generador de fixtures SSE |
| `backend/scripts/expire_waitlist.py` | Cron cleanup LFPDPPP |
| `backend/tests/test_waitlist.py` | Tests endpoint |
| `tests/specs/landing/` | Playwright E2E |
| `tests/specs/scan/sse-contract.spec.ts` | Snapshot test fixtures vs backend |
| `.github/workflows/lhci.yml` | Lighthouse CI gate |
| `docs/marketing/press-kit.md` | Boilerplate regulatorio |

### Modificar

| Archivo | Cambio |
|---|---|
| `frontend/app/(app)/page.tsx` | Mover a `(app)/home/page.tsx` |
| `frontend/app/(app)/layout.tsx:53-73` | Wordmark link `/` → `/home` |
| `frontend/components/BottomNav.tsx` | Item Home `/` → `/home` |
| `frontend/app/layout.tsx` | Metadata SEO/OG/Twitter |
| `frontend/lib/api/client.ts` | Login redirect `/` → `/home` |
| `backend/app/main.py` | Registrar router `waitlist` |
| Archivos del grep audit | Todos los `href="/"`, `router.push('/')`, `redirect('/')`, `page.goto('/')` |

### Reutilizar sin modificar

- `HomeOrbSection.tsx` (adapter en hero)
- `AvatarGlow.tsx`
- `SemaphoreBadge.tsx`
- `AILoadingState.tsx` (referencia visual para PipelineLoopAnim)
- `globals.css` (tokens, `.bs-*` utilities)
- `lib/stores/scanning.ts` (`useScanStore` — single source of truth)
- Backend: rate limiter, error schema, tablas existentes

---

## Pre-launch checklist (hard-gates — ningún código antes de estos)

- [ ] Spec aprobado (este documento)
- [ ] Plan ejecutable aprobado (`docs/superpowers/plans/`)
- [ ] Copy reescrito sin blocklist regulatorio — grep de verificación cero ocurrencias
- [ ] `scan-trace-*.json` fixtures generados desde 3 productos reales con backend corriendo local
- [ ] Grep audit ejecutado y lista de archivos a refactorizar confirmada
- [ ] Migración Alembic revisada y aplicada en local (UNIQUE LOWER(email), expires_at, consent_text)
- [ ] Cloudflare Turnstile site/secret keys configurados en env
- [ ] Counter ChromaDB verificado (`SELECT COUNT(*) FROM ingredients`)
- [ ] Press kit boilerplate listo + `press@bioshield.mx` configurado con SLA <4h
- [ ] Canales de distribución con owner + CAC + deadline asignados (tabla arriba)

---

## Verificación pre-ship

1. Redirect logic: sin flash de landing en `/` para usuario autenticado
2. Pipeline replay: 3 productos rotando con timing real, watermark visible
3. Waitlist flow: submit → 201; duplicado → 409; sin consent → 422; Turnstile fail → 422; rate limit → 429
4. Middleware exclusion: `/` sin JWT decode → p99 TTFB < 200ms
5. Regulatory grep: cero ocurrencias del blocklist en `(marketing)/` y `components/marketing/`
6. SSE contract test: fixtures vs backend schema → verde
7. LFPDPPP: cron elimina rows con `expires_at < NOW()` y sin `contacted_at`
8. Counter real: número en copy coincide con `SELECT COUNT(*) FROM ingredients`
9. Lighthouse CI: Performance ≥85 mobile, Accessibility ≥95, SEO =100
10. Multi-viewport: 375/768/1440/1920px sin cortes ni scroll horizontal
11. Accesibilidad: tab order, focus ring, skip-to-content, `prefers-reduced-motion`
12. Gap analysis demo-vs-real: claims/insights diff <30% en 3 productos

---

## Fuera de scope

- Stripe / billing / suscripciones
- i18n (español único)
- Email de confirmación de waitlist (v2)
- Blog / SEO long-tail
- A/B testing infrastructure
- Cookie banner (sin GA4 third-party)
- Cambios al design system (tokens, fuentes, glows)
- OAuth / login social
- App nativa (PWA cubre mobile)
