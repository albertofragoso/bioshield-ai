# BioShield AI — Design System

## Home Dashboard

**Layout:** Hero Orb con split panel responsive.

- **Mobile** (< `md`): columna centrada — orbe arriba, stats + historial abajo. Bottom nav fija.
- **Desktop** (≥ `md`): grid 50/50 — panel izquierdo con `HomeOrbSection`, panel derecho con `HomeStatsPanel`.

**CTA principal:** El orbe completo (`HomeOrbSection`) es un `<Link href="/scan">`. La mascota `/avatars/main.png` vive dentro del orbe.

**Animaciones activas en home:**

| Clase | Keyframe | Uso |
|---|---|---|
| `animate-glow-surge` | `glow-surge` | Orbe shell |
| `animate-pulse-ring` | `pulse-ring-out` | 2 rings expanding |
| `bs-orbital-ring-outer` | `bs-orbit-cw` | Ring exterior CW |
| `bs-orbital-ring-inner` | `bs-orbit-ccw` | Ring interior CCW |
| `animate-avatar-float` | `avatar-float` | Mascota |
| `scan-line` (via inline) | `scan-line` | Scan sweep periódica |
| `animate-float-p` | `float-p` | Partículas decorativas |
| `animate-data-tick` | `data-tick` | Data stream |
| `animate-fade-up` | `fade-up-kf` | Entrada de secciones |
| `animate-stagger-in` | `stagger-in-kf` | Filas del historial |

## Tokens

Ver `frontend/app/globals.css` y `docs/design/tokens.md`.
