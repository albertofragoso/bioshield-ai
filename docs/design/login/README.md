# Handoff: BioShield AI — `/login`

**Versión:** 1.0.0 · **Fecha:** 2026-04-21  
**Diseñado en:** Claude (Artifact HTML + React/Babel inline)  
**Implementar en:** Next.js (App Router)

---

## ⚠️ Importante — Sobre los archivos de diseño

Los archivos `.html` incluidos en este paquete son **prototipos de referencia**,
no código de producción. Están construidos con React + Babel inline para
demostración rápida. Tu tarea es **recrear estos diseños en Next.js** usando
los patrones, componentes y librerías ya establecidos en tu codebase.

**Fidelidad:** Alta (hifi). El diseño es pixel-perfect en colores, tipografía,
espaciado e interacciones. Implementa respetando los valores exactos del
`design-tokens.json`.

---

## 📁 Dónde colocar cada archivo en Next.js

### Tokens de diseño
```
your-nextjs-project/
├── tokens/
│   └── design-tokens.json        ← este archivo
```
Si usas **Tailwind CSS**, extiende `tailwind.config.ts` con estos valores.
Si usas **CSS Variables**, genera un `globals.css` a partir de ellos.

### Assets — Avatar mascota (piña)
```
your-nextjs-project/
├── public/
│   └── avatars/
│       ├── main.png    ← piña idle (ya procesada, sin fondo)
│       ├── mascot-happy.png      ← piña estado éxito
│       ├── mascot-error.png      ← piña estado error
│       └── mascot-loading.png    ← piña estado loading
```
> En Next.js, todo lo que vive en `/public` se sirve en la raíz `/`.
> Referencia como `src="/avatars/main.png"` en tu componente `<Image>`.

### Componentes
```
your-nextjs-project/
├── app/
│   └── (auth)/
│       └── login/
│           └── page.tsx          ← página principal de login
├── components/
│   └── auth/
│       ├── LoginCard.tsx         ← card contenedora
│       ├── LoginForm.tsx         ← formulario con campos y CTA
│       ├── AuthField.tsx         ← input reutilizable (email / password)
│       ├── AuthAlert.tsx         ← alert 401 / 429
│       └── NetworkToast.tsx      ← toast de error de red
├── hooks/
│   └── useLoginForm.ts           ← lógica del formulario y estados
```

### Fuentes (Google Fonts)
En `app/layout.tsx`:
```tsx
import { Pacifico, Space_Grotesk } from 'next/font/google';
// JetBrains Mono no está en next/font — usar @import en globals.css
```

---

## 🎨 Tokens de marca

Ver `design-tokens.json` para el listado completo. Resumen crítico:

| Token            | Valor                      | Uso                          |
|------------------|----------------------------|------------------------------|
| `--green`        | `#4ADE80`                  | CTA, bordes focus, glows     |
| `--amber`        | `#F59E0B`                  | Sufijo "AI", link registro   |
| `--teal`         | `#2DD4BF`                  | Link "Olvidaste contraseña"  |
| `--bg`           | `#080C07`                  | Background global            |
| `--surface`      | `#0D1310`                  | Card                         |
| `--text`         | `#DCF0DC`                  | Texto principal              |
| `--subtext`      | `#6B8A6A`                  | Labels, placeholders         |
| `font-display`   | Pacifico 400               | Wordmark "BioShield"         |
| `font-body`      | Space Grotesk 300–700      | Todo el resto                |
| `font-mono`      | JetBrains Mono 400–500     | Labels, alerts, metadata     |

---

## 🖥️ Pantalla: `/login`

### Layout
- Fondo global: `#080C07` con patrón hexagonal SVG + overlay scanlines
- Contenido: card centrada horizontal y verticalmente en el viewport
- Card: `max-width: 420px`, `border-radius: 18px`, `padding: 40px 36px 36px`
- Mobile (< 640px): card full-width con `padding: 28px 16px 24px`

### Fondo decorativo
```css
/* Hex grid pattern — aplicar al wrapper/layout */
background-image:
  radial-gradient(ellipse 70% 50% at 50% 0%, rgba(74,222,128,.08) 0%, transparent 65%),
  radial-gradient(ellipse 50% 40% at 80% 90%, rgba(245,158,11,.04) 0%, transparent 60%),
  url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='64'%3E%3Cpath d='M28 2 L54 17 L54 47 L28 62 L2 47 L2 17 Z' fill='none' stroke='rgba(74,222,128,0.04)' stroke-width='1'/%3E%3C/svg%3E");
background-size: auto, auto, 56px 64px;

/* Scanlines overlay (::after del wrapper) */
background: repeating-linear-gradient(
  0deg, transparent, transparent 3px,
  rgba(0,0,0,.03) 3px, rgba(0,0,0,.03) 4px
);
```

### Card
```css
background: #0D1310;
border: 1px solid rgba(74,222,128,.18);
border-radius: 18px;
box-shadow:
  0 0 0 1px rgba(74,222,128,.06),
  0 32px 80px rgba(0,0,0,.9),
  inset 0 0 60px rgba(74,222,128,.04);
backdrop-filter: blur(20px);
```

**Corner accents:** 4 esquinas con `position: absolute`, `60×60px`,
borde de 1px en `rgba(74,222,128,.35)` siguiendo la forma del card.

**Glow superior:**
```css
/* div absoluto centrado, top: -60px */
width: 260px; height: 140px;
background: radial-gradient(ellipse, rgba(74,222,128,.1) 0%, transparent 70%);
```

---

## 🍍 Avatar mascota

```tsx
// Usar next/image para optimización automática
import Image from 'next/image';

<Image
  src="/avatars/main.png"
  alt="BioShield mascot"
  width={140}
  height={140}
  style={{ objectFit: 'contain' }}
/>
```

**Animación wobble:**
```css
@keyframes wobble {
  0%   { transform: translateY(0)    rotate(-1.5deg); }
  20%  { transform: translateY(-7px) rotate(1.5deg);  }
  40%  { transform: translateY(-3px) rotate(-1deg);   }
  60%  { transform: translateY(-8px) rotate(2deg);    }
  80%  { transform: translateY(-2px) rotate(-1deg);   }
  100% { transform: translateY(0)    rotate(-1.5deg); }
}

.mascot-wrapper {
  animation: wobble 5s ease-in-out infinite;
  transform-origin: bottom center;
  /* Glow se aplica en mount vía transition */
  filter: drop-shadow(0 0 16px rgba(74,222,128,.5));
  transition: filter 1s ease;
}
/* Estado inicial sin glow → añadir glow en useEffect con delay 200ms */
```

> El PNG del avatar ya fue procesado con remoción de fondo (alpha transparente).
> **No aplicar** `mix-blend-mode` ni filtros CSS adicionales.

---

## 🔤 Wordmark

```tsx
<h1>
  <span style={{ fontFamily: 'Pacifico', fontSize: 28, color: '#4ADE80',
    textShadow: '0 0 30px rgba(74,222,128,.5)' }}>
    BioShield
  </span>
  <span style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 26,
    color: '#F59E0B', letterSpacing: '0.06em', marginLeft: 6,
    verticalAlign: 'middle' }}>
    AI
  </span>
</h1>

{/* Tagline */}
<p style={{ fontFamily: 'JetBrains Mono', fontSize: 9.5,
  color: '#6B8A6A', letterSpacing: '0.18em', textTransform: 'uppercase' }}>
  hack your nutrition ✦ protect your biology
</p>

{/* Divider */}
<div style={{ height: 1, marginTop: 24,
  background: 'linear-gradient(90deg, transparent, rgba(74,222,128,.2), transparent)' }}/>
```

---

## 📋 Formulario

### Campo genérico (`AuthField`)

**Props:** `label`, `type`, `value`, `onChange`, `error?`, `disabled?`,
`icon`, `rightSlot?`, `placeholder`

```css
/* Label */
font-family: JetBrains Mono;
font-size: 10px;
font-weight: 500;
text-transform: uppercase;
letter-spacing: 0.1em;
color: var(--subtext);           /* idle */
color: var(--green);             /* focus */
transition: color 0.2s;

/* Input wrapper */
background: rgba(0,0,0,.4);
border: 1.5px solid rgba(74,222,128,.15);   /* idle */
border: 1.5px solid #4ADE80;                /* focus */
border: 1.5px solid #F87171;                /* error */
border-radius: 8px;
padding: 0 14px;
box-shadow (focus): 0 0 0 3px rgba(74,222,128,.1), inset 0 0 20px rgba(74,222,128,.03);

/* Input text */
font-family: Space Grotesk;
font-size: 14px;
color: #DCF0DC;
padding: 14px 10px;
background: transparent;
outline: none;

/* Disabled */
opacity: 0.5;
```

**Campos:**
1. **Email** — icon: `<Mail size={15}/>` (Lucide), type: `email`
2. **Contraseña** — icon: `<Lock size={15}/>`, type: `password` / `text` con toggle,
   rightSlot: `<Eye>` / `<EyeOff>` (Lucide)

**Validación client-side:**
- Email: debe contener `@`
- Password: mínimo 8 caracteres
- Validar al hacer submit, no onChange

---

## 🔴 Alert (`AuthAlert`)

```tsx
// type: '401' | '429'
```

| Propiedad   | Error 401                                | Error 429                                  |
|-------------|------------------------------------------|--------------------------------------------|
| Bg          | `rgba(248,113,113,.08)`                  | `rgba(252,211,77,.08)`                     |
| Border      | `rgba(248,113,113,.3)`                   | `rgba(252,211,77,.3)`                      |
| Texto color | `#F87171`                                | `#FCD34D`                                  |
| Mensaje     | `[ERROR_401] Credenciales inválidas. Verifica tus datos.` | `[ERROR_429] Demasiados intentos. Espera 60 segundos.` |
| Font        | JetBrains Mono 11.5px                    | JetBrains Mono 11.5px                      |

Prefix `[ERROR_XXX]` en `font-weight: 700`, resto normal.

---

## 🔘 Botón CTA

```
Texto idle:    ⟶ entrar
Texto loading: <Spinner /> verificando…

font-family: JetBrains Mono
font-size: 13px
font-weight: 600
letter-spacing: 0.12em
text-transform: uppercase

background: rgba(74,222,128,.15)
border: 1.5px solid #4ADE80
border-radius: 10px
padding: 15px
width: 100%
color: #4ADE80

box-shadow idle:  0 0 20px rgba(74,222,128,.2)
box-shadow hover: 0 0 30px rgba(74,222,128,.35)
background hover: rgba(74,222,128,.25)

disabled:
  opacity: 0.5
  cursor: not-allowed
  box-shadow: none
```

**Spinner:** SVG con `animateTransform rotate`, dur `0.7s`, `stroke: currentColor`.

---

## 🌐 Toast — Sin conexión (`NetworkToast`)

```
Posición: fixed, bottom: 24px, left: 50%, translateX(-50%)
Mostrar: translateY(0) opacity 1
Ocultar: translateY(16px) opacity 0
Transition: all 0.3s ease

background: #111
border: 1px solid rgba(245,158,11,.3)
color: #F59E0B
border-radius: 10px
padding: 10px 18px
font-family: JetBrains Mono
font-size: 13px
Texto: <WifiOff size={14}/> sin_conexion_al_servidor
```

---

## 🔗 Links

```
"¿Olvidaste tu contraseña?" (placeholder, feature futuro)
  → align: right
  → color: #2DD4BF (teal)
  → font: JetBrains Mono 10.5px
  → letter-spacing: 0.04em
  → opacity: 0.8

"sin cuenta?  regístrate →"
  → align: center
  → font: JetBrains Mono 11px
  → "sin cuenta?" color: #6B8A6A
  → "regístrate →" color: #F59E0B, font-weight: 600
  → href: /register

Metadata footer:
  → "v1.0.0 · /login · POST /auth/login"
  → font: JetBrains Mono 9px
  → color: rgba(74,222,128,.2)
  → align: center
```

---

## ⚡ Estados de la UI

| Estado    | Trigger                    | Comportamiento                                                    |
|-----------|----------------------------|-------------------------------------------------------------------|
| `idle`    | Carga inicial              | Formulario limpio, botón activo                                   |
| `loading` | Submit del form            | Campos `disabled`, botón muestra spinner + "verificando…"         |
| `401`     | Response 401 de la API     | `<AuthAlert type="401"/>` sobre el form, campos re-habilitados    |
| `429`     | Response 429 de la API     | `<AuthAlert type="429"/>` sobre el form                           |
| `network` | Error de red / timeout     | `<NetworkToast/>` visible en bottom, formulario re-habilitado     |

---

## 🔌 Integración API

```ts
// hooks/useLoginForm.ts

const response = await fetch('/api/auth/login', {   // o tu proxy a POST /auth/login
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',    // ← CRÍTICO para recibir HTTP-only cookies
  body: JSON.stringify({ email, password }),
});

// Tokens (access_token, refresh_token) llegan como HTTP-only cookies.
// El frontend NO los lee ni almacena — llegan solos en el Set-Cookie header.
// Response shape en 200: { access_token, refresh_token, token_type, expires_in }
// No guardar nada de esto en localStorage ni state.

if (!response.ok) {
  if (response.status === 401) setError('401');
  if (response.status === 429) setError('429');
} else {
  router.push('/dashboard');  // o la ruta post-login
}
```

---

## 📦 Assets incluidos

| Archivo                          | Descripción                                      |
|----------------------------------|--------------------------------------------------|
| `design-tokens.json`             | Tokens de diseño (colores, tipos, spacing, etc.) |
| `README.md`                      | Este documento                                   |
| `reference/BioShield Login.html` | Prototipo interactivo de referencia              |

### Assets a colocar en `/public/avatars/` (proveídos por el cliente)

| Archivo                  | Estado de la app       |
|--------------------------|------------------------|
| `main.png`     | Idle / default         |
| `mascot-happy.png`       | Login exitoso          |
| `mascot-error.png`       | Error 401 / 429        |
| `mascot-loading.png`     | Loading / verificando  |

> El PNG ya fue procesado con remoción de fondo (transparencia alpha real).
> Resolución original: 992×1063px. Renderizar a 140×140px con `object-fit: contain`.

---

## ✅ Checklist de implementación

- [ ] Instalar fuentes: Pacifico, Space Grotesk, JetBrains Mono vía `next/font/google`
- [ ] Importar tokens en `tailwind.config.ts` o `globals.css`
- [ ] Copiar assets de mascota a `/public/avatars/`
- [ ] Crear `app/(auth)/login/page.tsx`
- [ ] Implementar `AuthField` con estados idle / focus / error / disabled
- [ ] Implementar `AuthAlert` para 401 y 429
- [ ] Implementar `NetworkToast` con transition de entrada/salida
- [ ] Implementar animación `wobble` del avatar + glow en mount
- [ ] Conectar `POST /auth/login` con `credentials: 'include'`
- [ ] Validar: email con `@`, password mínimo 8 chars, solo on submit
- [ ] Verificar que los tokens NO se lean del response body
- [ ] Probar responsive en 375px
- [ ] Probar todos los estados: idle, loading, 401, 429, network
