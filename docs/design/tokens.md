# BioShield AI — Design system tokens (Fase B)

**Versión:** 1.0 · **Fecha:** 2026-04-21
**Archivo fuente:** `frontend/app/globals.css`
**Referencia visual:** `frontend/temp/login/` (login ya implementado en Claude Design)

---

## Decisiones clave

| Dimensión | Decisión |
|---|---|
| Modo | **Dark-only** — no hay variante light, `<html class="dark">` forzado en `app/layout.tsx` |
| Primary | `#4ADE80` (green) — derivado del glow de DNA en el avatar mascota |
| Accents | `#F59E0B` (amber) + `#2DD4BF` (teal) |
| Fuentes | Pacifico (wordmark) + Space Grotesk (cuerpo) + JetBrains Mono (labels/meta) |
| Tono | Biotech hacker — glows, scanlines, hex-grid. Aplicado en todas las pantallas |
| Inter | **Retirada** del stack — reemplazada por Space Grotesk |

---

## Paleta de marca

| Token CSS | Tailwind class | HEX | Uso |
|---|---|---|---|
| `--brand-green` | `bg-brand-green` / `text-brand-green` | `#4ADE80` | CTA primario, bordes focus, glows, wordmark "BioShield" |
| `--brand-amber` | `bg-brand-amber` | `#F59E0B` | Sufijo "AI" del wordmark, links de registro, banners de expiración |
| `--brand-teal` | `bg-brand-teal` | `#2DD4BF` | Links secundarios ("Olvidaste tu contraseña") |
| `--brand-red` | `bg-brand-red` | `#F87171` | Alerts 401, estados de error |
| `--brand-amber-warn` | `bg-brand-amber-warn` | `#FCD34D` | Alerts 429 (rate limit) |

## Superficies

| Token | Tailwind | HEX | Uso |
|---|---|---|---|
| `--background` | `bg-background` | `#080C07` | Fondo global (con hex-grid + scanlines aplicados en `body`) |
| `--surface` | `bg-surface` / `bg-card` | `#0D1310` | Cards, popovers, inputs |
| `--foreground` | `text-foreground` | `#DCF0DC` | Texto principal |
| `--subtext` | `text-subtext` / `text-muted-foreground` | `#6B8A6A` | Labels, placeholders, metadata |
| `--border` | `border-border` | `rgba(74,222,128,0.18)` | Borde de card/input idle |
| `--ring` | `ring-ring` | `#4ADE80` | Ring de focus |

## Semáforo (ajustado para dark)

Los colores del plan original (`#EF4444`, `#EAB308`, etc.) corresponden a light mode. En dark, subimos luminancia y moderamos saturación para que no quemen contra `#080C07` y mantengan ratio WCAG AA.

| Estado | Token CSS | Tailwind | HEX | Ratio vs bg | Icono Lucide | Label ES |
|---|---|---|---|---|---|---|
| GRAY | `--semaphore-gray` | `bg-semaphore-gray` | `#A8B3A7` | 9.1:1 | `HelpCircle` | "Sin datos suficientes" |
| BLUE | `--semaphore-blue` | `bg-semaphore-blue` | `#60A5FA` | 7.2:1 | `CheckCircle` | "Seguro" |
| YELLOW | `--semaphore-yellow` | `bg-semaphore-yellow` | `#FACC15` | 13.4:1 | `AlertCircle` | "Precaución" |
| ORANGE | `--semaphore-orange` | `bg-semaphore-orange` | `#FB923C` | 9.0:1 | `AlertTriangle` | "Riesgo personal" |
| RED | `--semaphore-red` | `bg-semaphore-red` | `#F87171` | 6.8:1 | `ShieldAlert` | "Prohibido" |

**Regla de accesibilidad (WCAG AA):** nunca usar color como único indicador. Siempre acompañar con icono Lucide + label textual + (opcionalmente) avatar PNG.

---

## Tipografía

Cargadas en `app/layout.tsx` con `next/font/google`.

| Familia | Variable CSS | Tailwind | Pesos | Uso |
|---|---|---|---|---|
| Pacifico | `--font-pacifico` | `font-display` | 400 | Solo wordmark "BioShield". No usar para más. |
| Space Grotesk | `--font-space-grotesk` | `font-sans` | 300–700 | Cuerpo general: inputs, botones, párrafos, headings |
| JetBrains Mono | `--font-jetbrains-mono` | `font-mono` | 400–700 | Labels UPPERCASE, alerts `[ERROR_XXX]`, CAS numbers, E-numbers, barcodes, tagline |

### Escala tipográfica estándar

```
text-[9px]   → metadata footer (v1.0.0 · /login · POST /auth/login)
text-[9.5px] → tagline ("hack your nutrition ✦ protect your biology")
text-[10px]  → labels de inputs (JetBrains Mono UPPERCASE, tracking 0.1em)
text-xs   12 → chips, timestamps relativos
text-sm   14 → inputs (valor tipeado), cuerpo general
text-base 16 → párrafos, cuerpo
text-lg   18 → subtítulos
text-xl   20 → títulos de card
text-2xl  24 → título de pantalla
text-4xl  36 → hero headings (solo 1 por pantalla)
```

### Tracking (letter-spacing)

| Contexto | Tracking | Tailwind |
|---|---|---|
| Labels de input | `0.1em` | `tracking-[0.1em]` |
| Botón CTA | `0.12em` | `tracking-[0.12em]` |
| Tagline | `0.18em` | `tracking-[0.18em]` |
| "AI" del wordmark | `0.06em` | `tracking-[0.06em]` |

---

## Radios y espaciado

| Token | Tailwind | Valor | Uso |
|---|---|---|---|
| `--radius-card` | `rounded-card` | 18px | Card principal |
| `--radius-input` | `rounded-input` | 8px | Inputs, alerts |
| `--radius-button` | `rounded-button` | 10px | Botones |
| `--radius` | `rounded-lg` | 8px | Default shadcn |

Spacing: Tailwind default (`gap-4`, `p-6`, etc.). El login usa `padding: 40px 36px 36px` en card desktop y `28px 16px 24px` en mobile.

---

## Sombras y glows

Utilidades disponibles en `globals.css`:

| Clase | Equivalente CSS | Uso |
|---|---|---|
| `bs-card` | card completa con borde + sombra + backdrop-blur | Card de login, register, hero dashboard |
| `bs-glow-green` | `0 0 20px rgba(74,222,128,0.2)` | Botón CTA en idle |
| `bs-glow-green-strong` | `0 0 30px rgba(74,222,128,0.35)` | Botón CTA en hover |
| `bs-input-focus` | ring interno de focus | Input cuando está enfocado |
| `bs-mascot-glow` | `drop-shadow(0 0 16px rgba(74,222,128,0.5))` | Wrapper del `<Image/>` del avatar |

### Corner accents decorativos

Las 4 esquinas del card con `border` fluorescente. Usar como:

```tsx
<div className="bs-card relative">
  <span className="bs-corner bs-corner-tl" />
  <span className="bs-corner bs-corner-tr" />
  <span className="bs-corner bs-corner-bl" />
  <span className="bs-corner bs-corner-br" />
  {/* contenido */}
</div>
```

---

## Animaciones

| Clase Tailwind | Keyframes | Duración | Uso |
|---|---|---|---|
| `animate-wobble` | translateY + rotate 6-step | 5s infinite | Avatar mascota idle |
| `animate-scan-line` | translateY -100% → 100% | 2s linear infinite | Línea láser del barcode scanner |
| `animate-pulse-glow` | opacity + drop-shadow | 2.4s infinite | Avatar del semáforo en pantalla de resultado |
| `animate-pulse` (Tailwind) | opacity 1↔0.5 | 2s infinite | Semáforo al cambiar de color |

`transform-origin: bottom center` aplicado inline en el wrapper del avatar para que el wobble pivote desde la base de la piña.

---

## Fondos decorativos globales

Aplicados en `body` via `app/globals.css` — se heredan en **todas** las pantallas:

1. **Glow radial superior:** `radial-gradient(ellipse 70% 50% at 50% 0%, rgba(74,222,128,.08) 0%, transparent 65%)`
2. **Glow radial inferior derecho:** `radial-gradient(ellipse 50% 40% at 80% 90%, rgba(245,158,11,.04) 0%, transparent 60%)`
3. **Hex-grid pattern:** SVG 56×64px con trazo `rgba(74,222,128,0.04)`
4. **Scanlines overlay:** `repeating-linear-gradient` cada 4px en `body::after` (pointer-events none)

Nada de esto requiere wrappers extra en componentes — ya está aplicado globalmente.

---

## Avatares mascota (PNG en `/public/avatars/`)

| Archivo | Contexto de uso |
|---|---|
| `main.png` | Login, Register — hero con `animate-wobble` + `bs-mascot-glow` (140×140) |
| `welcome.png` | Dashboard primer login, empty states de onboarding |
| `progress.png` | Loading de `/scan` procesando foto (reemplaza skeleton genérico) |
| `success.png` | Toast/confirmación de biosync upload OK |
| `profile.png` | Avatar del usuario en header autenticado (40×40) |
| `support.png` | Empty state de errores, fallback 500 |
| `share.png` | Reservado — feature futuro "compartir scan" |
| `gray.png` / `blue.png` / `yellow.png` / `orange.png` / `red.png` | Hero del semáforo en `/scan/[id]` — **complementario** al badge color+icono+label, no reemplazo (WCAG AA) |

**Regla de uso del mascot de semáforo:** va **al lado** del círculo color + icono Lucide + label textual, nunca solo. Esto preserva el requisito de accesibilidad del plan (color no es único indicador).

```tsx
// Ejemplo estructura del hero de resultado
<div className="flex items-center gap-4">
  <Image src="/avatars/red.png" alt="" width={120} height={120} aria-hidden />
  <div>
    <div className="flex items-center gap-2">
      <ShieldAlert className="text-semaphore-red" />
      <span className="text-semaphore-red font-mono uppercase">Prohibido</span>
    </div>
    <h1>Producto no apto</h1>
  </div>
</div>
```

El PNG tiene `alt=""` + `aria-hidden` porque la información semántica ya la entregan icono + label (el avatar es decorativo).

---

## Checklist de uso en nuevas pantallas

- [ ] Importar clases de `globals.css` cuando necesite glows o corner accents
- [ ] Usar `font-display` SOLO para el wordmark "BioShield"
- [ ] Labels de inputs en `font-mono uppercase text-[10px] tracking-[0.1em]`
- [ ] Color de marca accesible via `text-brand-green`, `bg-brand-amber`, etc.
- [ ] Semáforo siempre: **color + icono Lucide + label textual** (+ opcional avatar PNG)
- [ ] Avatar mascota con `bs-mascot-glow` + `animate-wobble` (opcional según pantalla)
- [ ] Card principal con `bs-card` + 4 `bs-corner-*` si es card hero
- [ ] No añadir light mode — tokens son dark-only por diseño
