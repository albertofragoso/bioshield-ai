# BioShield AI — Scrollytelling Landing (Sección 2)

**Fecha:** 2026-05-24  
**Estado:** IMPLEMENTADO — branch `feature/scrollytelling-landing`  
**Reemplaza:** `RevealMomentStory` de `docs/superpowers/specs/2026-05-22-marketing-landing-design.md`

---

## Objetivo

Reemplazar la sección estática "El momento revelador" con una experiencia cinematográfica de 300vh que narre el problema de BioShield en 4 beats:

> Etiqueta limpia → aditivos ocultos → cruce con biomarcadores → veredicto personalizado.

---

## Decisiones de arquitectura

| Decisión | Elección | Razón |
|---|---|---|
| Engine de scroll | GSAP ScrollTrigger | Zero CLS en `force-static`; mejor scrub en iOS vs Framer Motion |
| Pin strategy | Full-grid pin (`pinSpacing: false`) | Ambas columnas se pinean juntas; evita que el right column se desplace mientras la izquierda queda fija |
| Fallback | `<StaticBeats />` | Mobile `< 1024px` y `prefers-reduced-motion: reduce` → sin GSAP, sin 300vh dead-scroll |
| Fixture de producto | Danone Yogurt Natural `7501055300072` | Producto real con 3 aditivos E407/E621/E202, validado en Open Food Facts |
| Compliance beat 3 | Datos ilustrativos + watermark permanente | Sin valores numéricos, sin claims causales |

---

## Estructura de archivos

```
frontend/components/marketing/
├── ScrollytellingSection.tsx   ← orquestador; GSAP init + fallback
├── NutritionLabelPanel.tsx     ← 4 capas absolutas (GSAP targets)
├── StaticBeats.tsx             ← fallback; BEATS constante compartida
├── ScrollyBeat.tsx             ← texto por beat con clase .scroll-beat-{i}
└── icons/
    ├── IconLabel.tsx           ← SVG nutrimental label
    ├── IconENumber.tsx         ← SVG número-E (aditivo)
    ├── IconBloodDrop.tsx       ← SVG gota de sangre con indicadores
    ├── IconShieldDNA.tsx       ← SVG shield + ADN
    └── index.ts
```

---

## 4 beats narrativos

| Beat | Título | Left panel state | Scroll zone |
|---|---|---|---|
| 1 | Lo que crees saber | `.label-clean` (claims marketing) | 0–25% |
| 2 | Lo que hay realmente | `.label-additives` + pills E407/E621/E202 | 25–50% |
| 3 | Lo que significa para ti | `.blood-overlay` (biomarkers ilustrativos) | 50–75% |
| 4 | La brecha cerrada | `.verdict-card` ("No recomendado") + CTA | 75–100% |

---

## Animaciones GSAP

### Pin
```
trigger: sectionRef, start: "top top", end: "bottom top"
pin: panelRef (envuelve ambas columnas), pinSpacing: false
```

El pin dura 300vh completos. `end: "bottom top"` asegura que el pin no se libere antes de que tl4 termine.

### Timelines de transición

| Timeline | Zona scroll | Qué anima |
|---|---|---|
| tl2 | 25–50% | `.label-clean` fade out → `.label-additives` fade in + pills float |
| tl3 | 50–75% | `.label-additives` dim 0.4 → `.blood-overlay` fade in |
| tl4 | 75–100% | `.blood-overlay` fade out → `.verdict-card` scale+fade in |

### Exit suave
```
trigger: sectionRef, start: "90% top", end: "bottom top", scrub: 1
panelRef → autoAlpha: 0, ease: "power1.in"
```

El full grid se desvanece en el último 10% del scroll, permitiendo que la siguiente sección ("Cómo te ayuda BioShield") entre desde abajo de forma gradual.

### Beat text fade-ins
Cada `.scroll-beat-{i}` tiene su propio `gsap.fromTo` scrubbed que lo lleva de `opacity:0.2` a `opacity:1` en su zona correspondiente.

---

## Bugs críticos resueltos durante implementación

### 1. Pin liberado antes de que beats 3-4 animaran
**Causa:** `end: "bottom bottom"` liberaba el pin a scrollY≈2431, antes de que tl3 (50-75%) y tl4 (75-100%) terminaran (≈3188).  
**Fix:** `end: "bottom top"` — el pin dura hasta que `section.bottom` alcanza `viewport.top`.

### 2. Left column sangrando en secciones posteriores (`pinSpacing: false` + translateY)
**Causa:** Con `pinSpacing: false`, GSAP aplica `translateY(sectionHeight)` al elemento pineado. Al liberar el pin, el translateY mantiene el panel cerca del viewport durante ~757px adicionales de scroll.  
**Fix:** Pinear el full-grid wrapper (ambas columnas juntas) + background opaco `#080C07` + `z-10` en `panelRef` + timeline scrubbed de exit para fade-out gradual.

### 3. `autoAlpha:0` persistente en React Strict Mode
**Causa:** `gsap.set()` dentro de callbacks `onLeave`/`onLeaveBack` no es rastreado por `gsap.context()`. En React 18 Strict Mode (double-invoke de effects), `ctx.revert()` no revierte el `autoAlpha:0` aplicado en el callback, y el valor persiste en el segundo mount.  
**Fix:** Usar `gsap.fromTo()` con `scrollTrigger.toggleActions` (ó timeline scrubbed) dentro del contexto — el tween SÍ es rastreado y `ctx.revert()` lo limpia correctamente.

---

## Consideraciones de compliance

- Beat 3: copy obligatorio → *"Si tu perfil muestra marcadores de inflamación elevados, BioShield cruza ese dato aquí — así se vería tu análisis."*
- Watermark permanente en `.blood-overlay`: *"Ejemplo ilustrativo · Datos reales solo con tu perfil activo"*
- Prohibido en cualquier beat: valores numéricos de biomarcadores, "activa vías", "aumenta PCR", "riesgo cardiovascular"

---

## Fallback mobile / reduced-motion

`<StaticBeats />` renderiza los 4 beats en columna única, sin GSAP, sin 300vh de scroll muerto. Los strings de los beats se exportan como constante `BEATS` en `StaticBeats.tsx` y son importados por `ScrollytellingSection.tsx` para evitar duplicación.

Condición de activación: `window.innerWidth < 1024` OR `prefers-reduced-motion: reduce`.

---

## Checklist de QA

- [x] Beats 1-4 transicionan con scrub en desktop
- [x] Panel no sangra en "Cómo te ayuda BioShield"
- [x] Transición de salida es gradual (fade-out 90-100%)
- [x] Mobile 375px: `<StaticBeats />` visible, sin GSAP, sin 300vh dead-scroll
- [x] `prefers-reduced-motion` → `<StaticBeats />` estático
- [x] Beat 3: ningún valor numérico, watermark visible
- [x] `RevealMomentStory` eliminado del DOM
- [x] `ctx.revert()` limpia correctamente en React Strict Mode
