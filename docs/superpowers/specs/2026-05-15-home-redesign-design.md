# BioShield Home — Redesign Spec

**Fecha:** 2026-05-15
**Rama:** `feat/home-redesign`
**Estado:** Aprobado — listo para implementación

---

## 1. Objetivo

Rediseñar `app/(app)/page.tsx` (Dashboard) para aumentar engagement visual mediante:
- Distribución más jerárquica centrada en la acción principal (escanear)
- Animaciones CSS ricas sin comprometer rendimiento (CSS-only, sin Framer Motion)
- Layout responsive real: split panel en desktop, columna con bottom nav en mobile

---

## 2. Decisiones de Diseño

| Decisión | Elección | Razón |
|---|---|---|
| Layout base | Hero Orb | El scan es la acción primaria — debe dominar visualmente |
| Responsive | Split panel ≥ `md` | Aprovecha el espacio horizontal en desktop sin romper la estética |
| Animaciones | Charged + scan-line periódica | Máximo impacto visual con CSS-only; prefers-reduced-motion safe |
| Navegación | Bottom nav en mobile | Mayor engagement y acceso directo a las 4 rutas principales |
| CTA visual | Mascota (`/avatars/main.png`) dentro del orbe | Identidad de marca, reemplaza ícono de cámara |

---

## 3. Layout

### Mobile (< `md`, columna única)

```
┌─────────────────────────────┐
│  Header: wordmark + salir   │
├─────────────────────────────┤
│  [scan-line periódica]      │
│  partículas flotantes       │
│  data stream decorativo     │
│                             │
│    "Toca para analizar"     │
│                             │
│   ┌──── Orbe ────┐         │
│   │  pulse rings  │         │
│   │  orbit CW/CCW │         │
│   │  mascota main │         │
│   └───────────────┘         │
│                             │
│   "Escanear producto"       │
│   "Barcode · Foto · IA"     │
│                             │
│  ┌──────┐  ┌──────────┐    │
│  │ 12   │  │ 47d      │    │
│  │Scans │  │Biomarcad.│    │
│  └──────┘  └──────────┘    │
│                             │
│  ┌─────────────────────┐   │
│  │ ⏱ Recientes         │   │
│  │ • Oatly Barista  2h │   │
│  │ • Doritos Nacho  1d │   │
│  │ • Red Bull SF    3d │   │
│  └─────────────────────┘   │
├─────────────────────────────┤
│  🏠 Home │📷 Scan│⏱│🧬   │  ← BottomNav
└─────────────────────────────┘
```

### Desktop (≥ `md`, split 50/50)

```
┌──────────────────────────────────────────────┐
│  Header: wordmark + salir                    │
├─────────────────────┬────────────────────────┤
│  [scan-line]        │                        │
│  partículas         │  Panel de salud        │
│  data stream        │                        │
│                     │  ┌──────┐ ┌──────────┐ │
│  "Toca para         │  │  12  │ │   47d    │ │
│   analizar"         │  │Scans │ │Biomarcad.│ │
│                     │  └──────┘ └──────────┘ │
│  ┌──── Orbe ──────┐ │                        │
│  │  pulse rings    │ │  🧬 Biomarcadores      │
│  │  orbit CW/CCW   │ │     activos · 47d     │
│  │  mascota main   │ │                        │
│  └─────────────────┘ │  ⏱ Recientes   Ver todo│
│                     │  • Oatly Barista  2h   │
│  "Escanear          │  • Doritos Nacho  1d   │
│   producto"         │  • Red Bull SF    3d   │
└─────────────────────┴────────────────────────┘
```

---

## 4. Stack de Animaciones

Todas CSS-only. Sin Framer Motion. Sin nuevas dependencias. Respetan `prefers-reduced-motion`.

| Nombre keyframe | Elemento | Duración | Loop |
|---|---|---|---|
| `glow-surge` | Orbe shell | 2.5s ease-in-out | ∞ |
| `pulse-ring-out` | 2 rings expanding desde orbe | 2.5s / offset 0.85s | ∞ |
| `orbit-cw` | Ring dashed exterior con dot | 12s linear | ∞ |
| `orbit-ccw` | Ring sólido interior con dot | 7s linear | ∞ |
| `avatar-float` | `<img>` mascota dentro del orbe | 4s ease-in-out | ∞ |
| `scan-sweep` | Línea horizontal de izq a der | 5s ease-in-out | ∞ |
| `float-p` | 4–5 partículas decorativas | 2.5s–4s staggered | ∞ |
| `data-tick` | Data stream decorativo | 1.5s ease-in-out | ∞ |
| `fade-up-kf` | Entrada de secciones | 0.45s staggered | 1 |
| `stagger-in` | Filas del historial | 0.4s staggered | 1 |

Keyframes `orbit-cw` y `orbit-ccw` ya existen en `globals.css` como `.bs-orbital-ring-outer` y `.bs-orbital-ring-inner` — se reutilizan.

---

## 5. Componentes Nuevos

### `components/BottomNav.tsx`
- Aparece solo en mobile (`md:hidden`)
- 4 items: Home `/` · Scan `/scan` · Historial `/history` · Biosync `/biosync`
- Active state: usa `usePathname()` para detectar ruta activa
- Glow drop-shadow en el icono activo
- Sticky bottom, `backdrop-filter: blur`

### `components/home/HomeOrbSection.tsx`
- Contiene: partículas, data stream, hint text, orbe con mascota y anillos
- El orbe completo es un `<Link href="/scan">` — toda el área es clickeable
- Recibe `className` para adaptar padding en mobile vs desktop
- La mascota es `<Image src="/avatars/main.png">` dentro del orbe circular

### `components/home/HomeStatsPanel.tsx`
- Recibe: `biosyncQuery`, `historyItems`, `historyEmpty`, `historyQuery.isLoading`
- Muestra: stats pills (count de scans cargados + biomarcadores), biosync card, historial reciente
- El stat de "Scans" usa `historyItems.length` de la query existente `getScanHistory(5)` — muestra 0–5, no requiere endpoint adicional. Label: "Recientes" no "Totales".
- Historial staggered con `animation-delay` por índice
- Reutiliza `SemaphoreBadge` para dots de color en historial

---

## 6. Modificaciones a Archivos Existentes

### `app/(app)/page.tsx`
- Rewrite completo — usa `HomeOrbSection` y `HomeStatsPanel`
- Grid responsive: `flex flex-col md:grid md:grid-cols-2 md:min-h-[calc(100vh-40px)]`
- Mantiene los dos `useQuery` existentes (`biosync-status`, `scan-history`)
- Misma lógica de `daysLeft`, `nearExpiry`, `historyEmpty` — solo cambia la presentación

### `app/(app)/layout.tsx`
- Agrega `<BottomNav />` antes del cierre de `</div>` del main
- Import del nuevo componente
- El header existente se mantiene sin cambios

### `app/globals.css`
- Agrega keyframes nuevos en sección `/* ---------- Keyframes ---------- */` existente:
  `glow-surge`, `pulse-ring-out`, `avatar-float`, `float-p`, `data-tick`, `fade-up-kf`, `stagger-in`
- Agrega clases utilitarias: `.animate-fade-up`, `.animate-stagger-in`, `.animate-float-p`
- No modifica keyframes existentes

---

## 7. Design Docs a Actualizar

- **`docs/design/README.md`**: agregar sección "Home Dashboard" con descripción del layout Hero Orb + split panel y referencia a componentes home/
- **`docs/architecture.md`**: sección Frontend → actualizar estructura de componentes con `components/home/` y `BottomNav`

---

## 8. Rama & Worktree

- **Rama base:** `main`
- **Rama de trabajo:** `feat/home-redesign`
- Worktree aislado — no interfiere con `feat/off-global-ingestion`
- Al completar: PR a `main` independiente del branch de ingestion
