# ADR: Frontend Custom Hooks Layer

**Fecha:** 2026-06-03  
**Estado:** Implementado  
**Scope:** `frontend/hooks/`

---

## Contexto

El análisis del grafo de código detectó acoplamiento `ui-dialog` ↔ `api-scan` (55 edges). Investigación reveló que ~45 son `import type` inocuos; los problemas reales:

1. **3 violations directas** — raw `await` de API functions en event handlers/useEffect sin pasar por React Query: `linkPhotoToBarcode`, `recordAnalyticsEvent`, `logout`.
2. **Cero abstracción de hooks** — cada página configuraba `useQuery`/`useMutation` con queryKeys, staleTime, y retry de forma independiente.

## Decisión

Crear `frontend/hooks/` como capa de abstracción que encapsula toda la configuración de TanStack Query. Ningún componente o página instancia `useQuery`/`useMutation` directamente.

## Implementación

### Hooks por dominio

| Archivo | Hooks | Key factory |
|---------|-------|-------------|
| `use-auth.ts` | `useLogin`, `useRegister`, `useLogout` | — |
| `use-biosync.ts` | `useBiomarkerStatus`, `useExtractBiomarkers`, `useUploadBiomarkers`, `useDeleteBiomarkers` | `biosyncKeys` |
| `use-scan.ts` | `useScanResult`, `useScanHistory`, `useAlternatives`, `useSharedScan`, `useLinkPhotoToBarcode`, `useCreateShareLink`, `useRevokeShareLink`, `useContributeToOff` | `scanKeys` |
| `use-analytics.ts` | `useRecordAnalyticsEvent` | — |

### Patrones críticos

**`useLogout` — nunca `queryClient.clear()`:**
```ts
onSuccess: async () => {
  await queryClient.cancelQueries()                    // cancela en vuelo PRIMERO
  queryClient.removeQueries({ predicate: () => true }) // limpia cache DESPUÉS
}
```
`clear()` sin cancelar queries en vuelo puede exponer datos del usuario anterior 200ms post-logout.

**Retry predicate — duck typing, no instanceof:**
```ts
retry: (_, err) => (err as { status?: number })?.status !== 404
```
`instanceof HttpError` falla en test environments con module isolation. Duck typing es más robusto.

**`*Keys` factories — fuente de verdad única:**
```ts
export const scanKeys = {
  result: (id: string) => ['scan', id] as const,
  history: (limit: number) => ['scan-history', limit] as const,
  ...
}
```
Elimina queryKeys hardcodeados dispersos. Todos los `invalidateQueries`/`prefetchQuery` usan estas factories.

**Callbacks en `mutate()`, no en el hook:**
Los callbacks de UI (toast, navigation, form errors) se pasan como segundo argumento a `mutate(vars, { onSuccess, onError })`, no al hook. El hook solo encapsula la lógica de dominio invariable.

## Tests

Vitest + `@testing-library/react`. 26 tests cubriendo:
- Comportamiento de queryKeys y staleTime
- Orden de `cancelQueries → removeQueries` en logout
- Retry predicate para 404
- Side effects de `invalidateQueries` en mutations

Configuración: `networkMode: 'always'` + `refetchOnWindowFocus: false` en `QueryClient` de tests para evitar flakiness en jsdom.

## Callsites refactorizados

**3 violations corregidas:**
- `app/(app)/layout.tsx` — `await logout()` → `useLogout().mutate()`
- `app/(app)/scan/[id]/page.tsx` (LinkBarcodeCard) — `await linkPhotoToBarcode()` → `useLinkPhotoToBarcode().mutate()`
- `app/(app)/scan/[id]/alternatives/page.tsx` — `recordAnalyticsEvent()` en useEffect → `useRecordAnalyticsEvent().mutate()`

**11 callsites refactorizados** en total (3 auth + 2 biosync + 6 scan/analytics).

## Enforcement

- `frontend/CLAUDE.md` — convención documentada
- `docs/architecture.md` sección 5.4 actualizada
- ESLint `no-restricted-imports` pendiente (próximo PR)
