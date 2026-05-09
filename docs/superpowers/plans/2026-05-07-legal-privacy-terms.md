# Legal: Política de Privacidad + Términos y Condiciones — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publicar páginas legales (/privacy, /terms) accesibles sin login, corregir el checkbox de términos en registro para deshabilitar el submit hasta que el usuario acepte, y añadir aviso de privacidad de Gemini en BioSync.

**Architecture:** Páginas autocontenidas bajo `(auth)/` (sin layout.tsx compartido), estilo visual idéntico a login/register. Contenido legal en `docs/legal/*.md` leído en build-time vía Server Components con `marked` para renderizado HTML. Sin cambios en backend ni DB.

**Tech Stack:** Next.js 15 App Router (Server Components), `marked` (markdown→HTML), `fs.readFileSync`, Playwright E2E, Tailwind CSS v4.

**Rama:** `feat/legal-privacy-terms` (worktree aislado, nunca sobre main)

---

## File Map

| Acción | Archivo |
|--------|---------|
| NUEVO | `docs/legal/privacy.md` |
| NUEVO | `docs/legal/terms.md` |
| NUEVO | `frontend/lib/legal-path.ts` |
| NUEVO | `frontend/app/(auth)/privacy/page.tsx` |
| NUEVO | `frontend/app/(auth)/terms/page.tsx` |
| NUEVO | `tests/specs/legal/legal-pages.spec.ts` |
| MOD | `frontend/app/(auth)/register/page.tsx` — línea 248 y 240-242 |
| MOD | `frontend/app/(app)/biosync/page.tsx` — función `PrivacyCard()` líneas 426-430 |
| MOD | `frontend/package.json` — agregar `marked` |
| MOD | `frontend/app/globals.css` — estilos `.legal-content` |

---

## Task 1: Instalar `marked` y crear helper de path

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/lib/legal-path.ts`

- [ ] **Step 1: Instalar dependencia**

```bash
cd frontend && pnpm add marked
```

Resultado esperado: `marked` aparece en `dependencies` de `package.json`.

- [ ] **Step 2: Crear helper de path**

Crear `frontend/lib/legal-path.ts`:

```ts
import path from 'path'

export function getLegalDocPath(filename: string): string {
  // process.cwd() en Next.js apunta a frontend/
  // '../docs/legal/' resuelve a la raíz del repo
  return path.join(process.cwd(), '..', 'docs', 'legal', filename)
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/lib/legal-path.ts
git commit -m "feat(legal): add marked dependency and legal-path helper"
```

---

## Task 2: Crear documentos legales en Markdown

**Files:**
- Create: `docs/legal/privacy.md`
- Create: `docs/legal/terms.md`

- [ ] **Step 1: Crear `docs/legal/privacy.md`**

```markdown
# Política de Privacidad

Última actualización: mayo 2026

En BioShield AI nos comprometemos a proteger tu información personal. Esta política describe qué datos recopilamos, cómo los usamos y cuáles son tus derechos.

## 1. Datos que recopilamos

- **Cuenta:** Tu dirección de email y contraseña (almacenada como hash bcrypt, nunca en texto plano).
- **Fotos de etiquetas:** Imágenes que subes para analizar ingredientes. Son procesadas por Google Gemini Vision y no se almacenan de forma permanente.
- **Datos de biomarcadores:** Los valores numéricos de tus análisis de sangre. Se encriptan con AES-256-GCM antes de guardarse y expiran automáticamente a los 180 días.

## 2. Cómo usamos tus datos

Utilizamos tus datos exclusivamente para ofrecerte el análisis nutricional personalizado dentro de la aplicación. No vendemos ni cedemos tu información a terceros con fines comerciales.

## 3. Terceros que procesan tus datos

- **Google Gemini API:** Analiza las imágenes de etiquetas y el texto de ingredientes que subes.
  **Importante:** Tus datos de biomarcadores NUNCA se envían a Gemini ni a ningún servicio de IA externo. Solo se procesan en nuestros servidores y se almacenan cifrados.
- **Open Food Facts:** Base de datos pública de productos alimenticios. Solo accedemos a ella cuando tú activas voluntariamente la opción de contribuir con ingredientes.

## 4. Retención y eliminación

- **Biomarcadores:** Se eliminan automáticamente 180 días después de subirlos.
- **Cuenta:** Para eliminar tu cuenta y todos tus datos, escríbenos a legal@bioshield.ai y lo procesaremos en un plazo de 30 días.

## 5. Seguridad

- Los datos médicos se encriptan en reposo usando AES-256-GCM.
- El acceso requiere autenticación JWT con expiración automática.
- Las contraseñas se almacenan como hashes bcrypt, nunca en texto plano.

## 6. Contacto

Para preguntas sobre esta política o para ejercer tus derechos, escríbenos a:

**legal@bioshield.ai**
```

- [ ] **Step 2: Crear `docs/legal/terms.md`**

```markdown
# Términos y Condiciones

Última actualización: mayo 2026

Al crear una cuenta en BioShield AI, aceptas los siguientes términos. Si no estás de acuerdo, no utilices el servicio.

## 1. Descripción del servicio

BioShield AI es una herramienta informativa de análisis nutricional. **No es un servicio médico, ni un sustituto de atención médica profesional.** Los análisis que proporciona son orientativos y no deben usarse para diagnóstico clínico ni tratamiento médico.

## 2. Uso aceptable

Al usar BioShield AI te comprometes a:

- No utilizar el servicio para diagnóstico clínico ni como sustituto de un profesional de la salud.
- No compartir tus credenciales de acceso con terceros.
- No intentar acceder a datos de otros usuarios.
- No usar el servicio para actividades ilegales o dañinas.

## 3. Limitación de responsabilidad

BioShield AI no se hace responsable de decisiones de salud tomadas en base a los análisis de la aplicación. Siempre consulta a un médico o nutriólogo certificado antes de modificar tu dieta o tratamiento médico.

## 4. Propiedad intelectual

- Los datos que subes (fotos, biomarcadores) son tuyos y permanecen de tu propiedad.
- El software, la marca BioShield AI, la interfaz y el diseño son propiedad exclusiva de BioShield AI.

## 5. Modificaciones

Nos reservamos el derecho de actualizar estos términos en cualquier momento. Te notificaremos por email ante cambios sustanciales. El uso continuado del servicio implica la aceptación de los nuevos términos.

## 6. Contacto

Para preguntas sobre estos términos, escríbenos a:

**legal@bioshield.ai**
```

- [ ] **Step 3: Commit**

```bash
git add docs/legal/
git commit -m "docs(legal): add privacy policy and terms of service markdown sources"
```

---

## Task 3: Estilos globales para `.legal-content`

**Files:**
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Agregar estilos para contenido markdown legal**

Abrir `frontend/app/globals.css` y añadir al final:

```css
/* ── Legal pages markdown rendering ──────────────────────── */
.legal-content h1 {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--foreground);
  margin-bottom: 0.5rem;
}
.legal-content h2 {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--foreground);
  margin-top: 1.5rem;
  margin-bottom: 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.legal-content p {
  margin-bottom: 0.75rem;
  line-height: 1.7;
}
.legal-content ul {
  margin-bottom: 0.75rem;
  padding-left: 1rem;
}
.legal-content li {
  margin-bottom: 0.4rem;
  line-height: 1.6;
}
.legal-content strong {
  color: var(--foreground);
  font-weight: 600;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/globals.css
git commit -m "style(legal): add legal-content markdown styles"
```

---

## Task 4: Escribir tests E2E (failing first)

**Files:**
- Create: `tests/specs/legal/legal-pages.spec.ts`

- [ ] **Step 1: Crear el spec**

Crear `tests/specs/legal/legal-pages.spec.ts`:

```ts
import { test, expect } from '@playwright/test'

test.describe('Legal pages', () => {
  test('/privacy loads with correct heading and avatar', async ({ page }) => {
    await page.goto('/privacy')
    await expect(page.getByRole('heading', { name: 'Política de Privacidad' })).toBeVisible()
    await expect(page.getByAltText('BioShield soporte')).toBeVisible()
  })

  test('/privacy contains biomarker privacy statement', async ({ page }) => {
    await page.goto('/privacy')
    await expect(page.getByText(/biomarcadores NUNCA se envían a Gemini/i)).toBeVisible()
  })

  test('/terms loads with correct heading and avatar', async ({ page }) => {
    await page.goto('/terms')
    await expect(page.getByRole('heading', { name: 'Términos y Condiciones' })).toBeVisible()
    await expect(page.getByAltText('BioShield perfil')).toBeVisible()
  })

  test('/terms contains medical disclaimer', async ({ page }) => {
    await page.goto('/terms')
    await expect(page.getByText(/No es un servicio médico/i)).toBeVisible()
  })

  test('/privacy back link navigates to register', async ({ page }) => {
    await page.goto('/privacy')
    const backLink = page.getByRole('link', { name: /volver al registro/i })
    await expect(backLink).toHaveAttribute('href', '/register')
  })

  test('/terms back link navigates to register', async ({ page }) => {
    await page.goto('/terms')
    const backLink = page.getByRole('link', { name: /volver al registro/i })
    await expect(backLink).toHaveAttribute('href', '/register')
  })
})

test.describe('Register — terms consent', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/register')
  })

  test('submit button is disabled when checkbox is unchecked', async ({ page }) => {
    const submitBtn = page.getByRole('button', { name: /crear cuenta/i })
    await expect(submitBtn).toBeDisabled()
  })

  test('submit button enables after checking terms checkbox', async ({ page }) => {
    const submitBtn = page.getByRole('button', { name: /crear cuenta/i })
    await expect(submitBtn).toBeDisabled()

    // Click the custom checkbox label
    await page.getByText(/acepto la/i).click()
    await expect(submitBtn).toBeEnabled()
  })

  test('register checkbox has link to /privacy', async ({ page }) => {
    await expect(page.getByRole('link', { name: /política de privacidad/i }))
      .toHaveAttribute('href', '/privacy')
  })

  test('register checkbox has link to /terms', async ({ page }) => {
    await expect(page.getByRole('link', { name: /términos y condiciones/i }))
      .toHaveAttribute('href', '/terms')
  })
})

test.describe('BioSync — privacy card', () => {
  test('privacy card mentions Gemini explicitly', async ({ page, context }) => {
    // Set auth cookie so (app) route is accessible
    await context.addCookies([{
      name: 'access_token',
      value: 'test-token',
      domain: 'localhost',
      path: '/',
    }])
    await page.goto('/biosync')
    await expect(page.getByText(/Gemini/i)).toBeVisible()
  })
})
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```bash
cd /path/to/repo && pnpm exec playwright test tests/specs/legal/ --reporter=line
```

Resultado esperado: todos los tests FAIL (páginas no existen aún). Si alguno pasa inesperadamente, investigar antes de continuar.

- [ ] **Step 3: Commit**

```bash
git add tests/specs/legal/
git commit -m "test(legal): add failing E2E specs for privacy/terms pages and register consent"
```

---

## Task 5: Crear página /privacy

**Files:**
- Create: `frontend/app/(auth)/privacy/page.tsx`

- [ ] **Step 1: Crear la página**

Crear `frontend/app/(auth)/privacy/page.tsx`:

```tsx
import fs from 'fs'
import Link from 'next/link'
import Image from 'next/image'
import { marked } from 'marked'
import { getLegalDocPath } from '@/lib/legal-path'

export default async function PrivacyPage() {
  const raw = fs.readFileSync(getLegalDocPath('privacy.md'), 'utf-8')
  const html = await marked(raw)

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-8 relative z-10">
      <div className="relative w-full max-w-[560px]">
        {/* Glow superior */}
        <div
          className="absolute left-1/2 -translate-x-1/2 pointer-events-none"
          style={{
            top: "-60px",
            width: "260px",
            height: "140px",
            background: "radial-gradient(ellipse, rgba(74,222,128,.1) 0%, transparent 70%)",
          }}
        />

        {/* Card */}
        <div className="bs-card relative overflow-hidden px-[36px] py-[40px] max-sm:px-[16px] max-sm:py-[28px]">
          <span className="bs-corner bs-corner-tl" />
          <span className="bs-corner bs-corner-tr" />
          <span className="bs-corner bs-corner-bl" />
          <span className="bs-corner bs-corner-br" />

          {/* Avatar */}
          <div className="flex flex-col items-center gap-3 mb-6">
            <Image
              src="/avatars/support.png"
              alt="BioShield soporte"
              width={100}
              height={107}
              className="object-contain"
              priority
            />
            <div className="text-center">
              <h1 className="font-sans font-bold text-[22px] text-foreground">
                Política de Privacidad
              </h1>
              <p className="font-mono text-[10px] text-subtext tracking-[0.1em] uppercase mt-1">
                Última actualización: mayo 2026
              </p>
            </div>
            <div
              className="w-full h-px mt-1"
              style={{ background: "linear-gradient(90deg, transparent, rgba(74,222,128,.2), transparent)" }}
            />
          </div>

          {/* Markdown content */}
          <div
            className="legal-content font-mono text-[12px] leading-[1.7] text-subtext"
            dangerouslySetInnerHTML={{ __html: html }}
          />

          {/* Back link */}
          <div className="mt-8 text-center">
            <Link
              href="/register"
              className="font-mono text-[11px] text-brand-amber hover:opacity-80 transition-opacity"
            >
              ← volver al registro
            </Link>
          </div>

          <p
            className="mt-4 text-center font-mono text-[9px]"
            style={{ color: "rgba(74,222,128,.2)" }}
          >
            v1.0.0 · /privacy · legal@bioshield.ai
          </p>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Ejecutar tests de /privacy**

```bash
pnpm exec playwright test tests/specs/legal/ -g "privacy" --reporter=line
```

Resultado esperado: los 3 tests de `/privacy` pasan.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(auth\)/privacy/
git commit -m "feat(legal): add /privacy page with support avatar and markdown content"
```

---

## Task 6: Crear página /terms

**Files:**
- Create: `frontend/app/(auth)/terms/page.tsx`

- [ ] **Step 1: Crear la página**

Crear `frontend/app/(auth)/terms/page.tsx`:

```tsx
import fs from 'fs'
import Link from 'next/link'
import Image from 'next/image'
import { marked } from 'marked'
import { getLegalDocPath } from '@/lib/legal-path'

export default async function TermsPage() {
  const raw = fs.readFileSync(getLegalDocPath('terms.md'), 'utf-8')
  const html = await marked(raw)

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-8 relative z-10">
      <div className="relative w-full max-w-[560px]">
        {/* Glow superior */}
        <div
          className="absolute left-1/2 -translate-x-1/2 pointer-events-none"
          style={{
            top: "-60px",
            width: "260px",
            height: "140px",
            background: "radial-gradient(ellipse, rgba(74,222,128,.1) 0%, transparent 70%)",
          }}
        />

        {/* Card */}
        <div className="bs-card relative overflow-hidden px-[36px] py-[40px] max-sm:px-[16px] max-sm:py-[28px]">
          <span className="bs-corner bs-corner-tl" />
          <span className="bs-corner bs-corner-tr" />
          <span className="bs-corner bs-corner-bl" />
          <span className="bs-corner bs-corner-br" />

          {/* Avatar */}
          <div className="flex flex-col items-center gap-3 mb-6">
            <Image
              src="/avatars/profile.png"
              alt="BioShield perfil"
              width={100}
              height={107}
              className="object-contain"
              priority
            />
            <div className="text-center">
              <h1 className="font-sans font-bold text-[22px] text-foreground">
                Términos y Condiciones
              </h1>
              <p className="font-mono text-[10px] text-subtext tracking-[0.1em] uppercase mt-1">
                Última actualización: mayo 2026
              </p>
            </div>
            <div
              className="w-full h-px mt-1"
              style={{ background: "linear-gradient(90deg, transparent, rgba(74,222,128,.2), transparent)" }}
            />
          </div>

          {/* Markdown content */}
          <div
            className="legal-content font-mono text-[12px] leading-[1.7] text-subtext"
            dangerouslySetInnerHTML={{ __html: html }}
          />

          {/* Back link */}
          <div className="mt-8 text-center">
            <Link
              href="/register"
              className="font-mono text-[11px] text-brand-amber hover:opacity-80 transition-opacity"
            >
              ← volver al registro
            </Link>
          </div>

          <p
            className="mt-4 text-center font-mono text-[9px]"
            style={{ color: "rgba(74,222,128,.2)" }}
          >
            v1.0.0 · /terms · legal@bioshield.ai
          </p>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Ejecutar tests de /terms**

```bash
pnpm exec playwright test tests/specs/legal/ -g "terms" --reporter=line
```

Resultado esperado: los 3 tests de `/terms` pasan.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(auth\)/terms/
git commit -m "feat(legal): add /terms page with profile avatar and markdown content"
```

---

## Task 7: Corregir register — disabled y links en checkbox

**Files:**
- Modify: `frontend/app/(auth)/register/page.tsx` — líneas 240–242 y 248

**Contexto:** El checkbox ya existe con `const [accepted, setAccepted] = useState(false)` y la validación `if (!accepted)` en `handleSubmit`. Solo falta (a) deshabilitar el botón visualmente y (b) agregar links reales en el label.

- [ ] **Step 1: Actualizar label del checkbox (líneas 240-242)**

Cambiar:
```tsx
<span className="font-mono text-[11px] text-subtext select-none">
  acepto los términos y la política de datos médicos
</span>
```

Por:
```tsx
<span className="font-mono text-[11px] text-subtext select-none">
  acepto la{" "}
  <Link
    href="/privacy"
    target="_blank"
    onClick={(e) => e.stopPropagation()}
    className="text-brand-amber underline hover:opacity-80 transition-opacity"
  >
    política de privacidad
  </Link>
  {" "}y los{" "}
  <Link
    href="/terms"
    target="_blank"
    onClick={(e) => e.stopPropagation()}
    className="text-brand-amber underline hover:opacity-80 transition-opacity"
  >
    términos y condiciones
  </Link>
</span>
```

> **Nota:** `e.stopPropagation()` en los links evita que el click en el link marque/desmarque el checkbox.

- [ ] **Step 2: Actualizar disabled del botón submit (línea 248)**

Cambiar:
```tsx
disabled={isPending}
```

Por:
```tsx
disabled={isPending || !accepted}
```

- [ ] **Step 3: Verificar que `Link` ya está importado**

La línea 6 del archivo tiene:
```tsx
import Link from "next/link";
```
✅ Ya está — no agregar import duplicado.

- [ ] **Step 4: Ejecutar tests de register**

```bash
pnpm exec playwright test tests/specs/legal/ -g "Register" --reporter=line
```

Resultado esperado: los 4 tests de register pasan.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\(auth\)/register/page.tsx
git commit -m "fix(legal): gate register submit on terms checkbox + add privacy/terms links"
```

---

## Task 8: Actualizar PrivacyCard en BioSync

**Files:**
- Modify: `frontend/app/(app)/biosync/page.tsx` — función `PrivacyCard()` líneas 426-430

- [ ] **Step 1: Reemplazar el array de bullets**

Cambiar:
```tsx
{[
  "Encriptados con AES-256 antes de guardarse.",
  "Se borran automáticamente después de 180 días.",
  "Nunca se comparten ni se usan para entrenar modelos.",
  "Puedes eliminarlos en cualquier momento.",
]}
```

Por:
```tsx
{[
  "Encriptados con AES-256 antes de guardarse.",
  "Se borran automáticamente después de 180 días.",
  "Nunca se comparten con terceros ni con servicios de IA externos (incluyendo Gemini).",
  "Nunca se usan para entrenar modelos.",
  "Puedes eliminarlos en cualquier momento.",
]}
```

- [ ] **Step 2: Ejecutar test de BioSync**

```bash
pnpm exec playwright test tests/specs/legal/ -g "BioSync" --reporter=line
```

Resultado esperado: el test de BioSync pasa.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/biosync/page.tsx
git commit -m "feat(legal): add Gemini privacy notice to BioSync PrivacyCard"
```

---

## Task 9: Verificación final

- [ ] **Step 1: Correr todos los tests legales**

```bash
pnpm exec playwright test tests/specs/legal/ --reporter=line
```

Resultado esperado: **todos los tests pasan**.

- [ ] **Step 2: Correr suite completa para detectar regresiones**

```bash
pnpm exec playwright test --reporter=line
```

Resultado esperado: misma cantidad de tests pasando que antes de esta implementación. Si algo falla que pasaba antes, investigar antes de abrir PR.

- [ ] **Step 3: Verificar build de producción**

```bash
cd frontend && pnpm build
```

Resultado esperado: build termina sin errores de TypeScript ni de `fs.readFileSync` (el path helper debe resolver correctamente desde `frontend/`).

- [ ] **Step 4: Abrir PR hacia main**

```bash
gh pr create \
  --title "feat(legal): publish privacy policy and T&C pages" \
  --body "Closes legal blocker for Fase 2 launch.

## Changes
- Add /privacy and /terms public pages (auth layout, markdown-rendered)
- Fix register submit disabled until terms accepted
- Add explicit Gemini privacy notice to BioSync PrivacyCard
- Add E2E tests for all legal flows

## Legal content
Stored in docs/legal/{privacy,terms}.md — editable without touching components.

## Future debt
See docs/superpowers/specs/2026-05-07-legal-privacy-terms-design.md § Deuda técnica futura" \
  --base main
```

---

## Gotchas recordatorio

| # | Gotcha | Ya considerado en el plan |
|---|--------|--------------------------|
| 1 | Register submit no checkeaba `accepted` | Task 7 fix `disabled={isPending \|\| !accepted}` |
| 2 | No existe `(auth)/layout.tsx` | Páginas autocontenidas en Tasks 5 y 6 |
| 3 | `react-markdown` ESM issues | Usamos `marked` (CJS compatible) en Task 1 |
| 4 | BioSync ya tiene `PrivacyCard()` | Task 8 modifica bullets existentes |
| 5 | Links dentro de `<label>` disparan el checkbox | `e.stopPropagation()` en Task 7 |
