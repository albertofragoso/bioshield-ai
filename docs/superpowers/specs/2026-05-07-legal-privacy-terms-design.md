# Legal: Política de Privacidad + Términos y Condiciones

**Fecha:** 2026-05-07
**Estado:** Aprobado — listo para implementación
**Rama:** `feat/legal-privacy-terms` (nunca sobre `main`)
**Bloqueante de:** Fase 2 / lanzamiento público

---

## Contexto

BioShield AI maneja datos de salud sensibles (biomarcadores encriptados AES-256, fotos de etiquetas procesadas por Gemini). El PRD identifica los documentos legales como el único bloqueante para el lanzamiento de Fase 2.

**Nivel de cumplimiento elegido: D — "algo publicado para lanzar"**
Texto credible y funcional. Sin infraestructura de consentimiento compleja. Ver sección de deuda técnica para el camino de actualización.

---

## Alcance

### Archivos nuevos
| Archivo | Descripción |
|---------|-------------|
| `docs/legal/privacy.md` | Fuente de verdad de la Política de Privacidad |
| `docs/legal/terms.md` | Fuente de verdad de los Términos y Condiciones |
| `frontend/lib/legal-path.ts` | Helper de path para leer `docs/legal/` desde Next.js |
| `frontend/app/(auth)/privacy/page.tsx` | Página pública — Política de Privacidad |
| `frontend/app/(auth)/terms/page.tsx` | Página pública — Términos y Condiciones |

### Archivos modificados
| Archivo | Cambio |
|---------|--------|
| `frontend/app/(auth)/register/page.tsx` | Fix `disabled={isPending || !accepted}` + links a `/privacy` y `/terms` en label existente |
| `frontend/app/(app)/biosync/page.tsx` | Añadir bullet "biomarcadores nunca se comparten con Gemini" en `PrivacyCard()` existente |
| `frontend/package.json` | `+react-markdown` |

### Sin cambios
- Backend (FastAPI) — ninguno
- Base de datos / migraciones Alembic — ninguna
- Zustand / TanStack Query — ninguno

---

## Decisiones de diseño

### Contenido legal
- **Jurisdicción:** Nivel D — texto estándar mejorado, sin estructura GDPR/CCPA formal
- **Contacto legal:** `legal@bioshield.ai`
- **Idioma:** Español

### UI / UX
- **Consentimiento en registro:** Checkbox inline ya existente en `register/page.tsx`. Solo fix al `disabled` y actualización del label con links reales.
- **Layout de páginas legales:** Páginas autocontenidas (no hay `(auth)/layout.tsx`), mismo estilo visual que login/register.
- **Avatar `/privacy`:** `support.png` — tono de confianza
- **Avatar `/terms`:** `profile.png` — tono de identidad/contrato
- **BioSync:** Actualizar `PrivacyCard()` existente, no crear componente nuevo.

### Arquitectura de contenido
Los `.md` viven en `docs/legal/` (raíz del repo). Next.js los lee en build-time vía `fs.readFileSync` desde un Server Component, usando el helper:

```ts
// frontend/lib/legal-path.ts
import path from 'path'

export function getLegalDocPath(filename: string): string {
  return path.join(process.cwd(), '..', 'docs', 'legal', filename)
}
```

`process.cwd()` en Next.js apunta a `frontend/` durante el build, por lo que `..` resuelve a la raíz del repo.

**Ventaja:** Un abogado puede editar `docs/legal/privacy.md` sin tocar código TypeScript.

### Dependencia nueva
- `react-markdown` — para renderizar el contenido Markdown en los Server Components de las páginas legales.

---

## Estructura de los documentos legales

### `docs/legal/privacy.md`

```
1. Qué datos recopilamos
   - Email y contraseña (hash bcrypt, nunca en texto plano)
   - Fotos de etiquetas (procesadas por Gemini Vision, no almacenadas permanentemente)
   - Datos de biomarcadores (encriptados AES-256-GCM, expiran en 180 días)

2. Cómo los usamos
   - Únicamente para el análisis nutricional personalizado dentro de la app

3. Terceros que procesan tus datos
   - Google Gemini API — análisis de imágenes de etiquetas y texto de ingredientes
     ⚠️ Tus datos de biomarcadores NUNCA se envían a Gemini ni a ningún tercero.
        Solo se procesan en nuestros servidores y se almacenan encriptados.
   - Open Food Facts — base de datos pública, solo si el usuario activa la contribución

4. Retención y eliminación
   - Biomarcadores: eliminados automáticamente a los 180 días
   - Cuenta: escribe a legal@bioshield.ai para eliminar tu cuenta y todos tus datos

5. Seguridad
   - Datos médicos encriptados en reposo (AES-256-GCM)
   - Acceso autenticado vía JWT con expiración automática

6. Contacto
   - legal@bioshield.ai
```

### `docs/legal/terms.md`

```
1. Descripción del servicio
   - BioShield es una herramienta informativa, NO un servicio médico

2. Uso aceptable
   - No usar para diagnóstico clínico ni como sustituto de atención médica
   - No compartir credenciales de acceso

3. Limitación de responsabilidad
   - Los análisis son orientativos; consulta siempre a un profesional de salud

4. Propiedad intelectual
   - El contenido generado a partir de los datos del usuario permanece del usuario
   - El software, marca e interfaz son propiedad de BioShield

5. Modificaciones
   - Nos reservamos el derecho de actualizar estos términos
   - Notificación por email ante cambios sustanciales

6. Contacto
   - legal@bioshield.ai
```

---

## Gotchas identificados

| # | Gotcha | Impacto | Resolución |
|---|--------|---------|------------|
| 1 | Register ya tiene checkbox pero `disabled` no lo checa | **Crítico** | Fix `disabled={isPending \|\| !accepted}` + agregar links |
| 2 | No existe `(auth)/layout.tsx` | **Importante** | Páginas autocontenidas, no heredan layout |
| 3 | `react-markdown` no instalada | **Importante** | `pnpm add react-markdown` antes de crear páginas |
| 4 | BioSync ya tiene `PrivacyCard()` | Info / buena noticia | Solo agregar bullet, no crear componente |

---

## Flujo de navegación

```
/register ──(link en checkbox)──► /privacy  (target="_blank")
           ──(link en checkbox)──► /terms   (target="_blank")

/privacy ─────────────────────── página pública, sin login requerido
/terms ───────────────────────── página pública, sin login requerido
```

---

## Deuda técnica futura

Documentada aquí para que no se pierda. Abordar antes de escalar a usuarios reales o inversión.

| Ítem | Prioridad | Descripción |
|------|-----------|-------------|
| Revisión por abogado | Alta | Reemplazar el texto actual por versión revisada legalmente |
| `users.terms_accepted_at` + `terms_version` | Media | Migración Alembic: registrar cuándo y qué versión aceptó cada usuario |
| `users.consent_version` | Media | Forzar re-aceptación si los T&C cambian |
| `GET /user/data` | Media | Endpoint de portabilidad de datos (GDPR Art. 20) |
| `DELETE /user/account` | Media | Endpoint de derecho al olvido (GDPR Art. 17) |
| Audit log de acceso a datos médicos | Media | Tabla `data_access_log` para trazabilidad |
| Cobertura GDPR formal | Baja-Media | Si hay usuarios en UE: DPA, registro de actividades de tratamiento |
| Cobertura CCPA | Baja | Si hay usuarios en California |
| Cobertura LGPD | Baja | Si hay usuarios en Brasil |
| Notificación de cambios en T&C por email | Baja | Backend: trigger de email cuando se actualiza `terms_version` |

---

## Flujo de trabajo

- Rama: `feat/legal-privacy-terms` (creada desde `main` vía worktree)
- Nunca commitear directamente sobre `main`
- PR hacia `main` al finalizar, con review antes de merge
