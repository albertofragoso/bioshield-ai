# Home Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rediseñar `app/(app)/page.tsx` — Hero Orb con mascota, split panel desktop, charged CSS animations, bottom nav mobile.

**Architecture:** `page.tsx` mantiene los dos `useQuery` existentes y delega presentación a dos componentes: `HomeOrbSection` (CTA de scan con orbe animado) y `HomeStatsPanel` (stats + biosync + historial). `BottomNav` se agrega a `layout.tsx` como `fixed bottom-0 md:hidden`. Todo el stack de animaciones vive en `globals.css` como keyframes + utility classes.

**Tech Stack:** Next.js 16 App Router, Tailwind CSS v4, CSS-only animations, Playwright (E2E), TypeScript strict.

**Worktree:** `.claude/worktrees/home-redesign/` — rama `feat/home-redesign`. Todos los comandos se ejecutan desde ahí salvo que se indique lo contrario.

---

### Task 1: Actualizar E2E tests — dashboard (TDD: escribir primero)

**Files:**
- Modify: `tests/specs/dashboard/dashboard.spec.ts`

- [ ] **Step 1: Reemplazar el archivo con los tests actualizados**

Los tests existentes asumen el layout antiguo (texto "sin scans aún", ausencia de bottom nav). Actualizar para cubrir el nuevo diseño.

```typescript
import {
  test,
  expect,
  mockBiosyncStatus,
  mockScanHistory,
  makeBiomarkerStatus,
  makeScanHistoryEntry,
} from "../../fixtures";

test.describe("Feature: Dashboard", () => {
  test("happy path — orb CTA links to /scan", async ({ mockedPage }) => {
    await mockBiosyncStatus(mockedPage, makeBiomarkerStatus({ has_data: false }));
    await mockScanHistory(mockedPage, []);
    await mockedPage.goto("/");

    const orbLink = mockedPage.getByRole("link", { name: /escanear producto/i }).first();
    await expect(orbLink).toBeVisible();
    await expect(orbLink).toHaveAttribute("href", "/scan");
  });

  test("happy path — populated dashboard shows biomarker card and recent scans", async ({ mockedPage }) => {
    await mockBiosyncStatus(mockedPage, makeBiomarkerStatus({ has_data: true }));
    await mockScanHistory(mockedPage, [
      makeScanHistoryEntry({ id: "s1", product_name: "Producto Alpha", semaphore: "YELLOW" }),
      makeScanHistoryEntry({ id: "s2", product_name: "Producto Beta", semaphore: "RED" }),
    ]);
    await mockedPage.goto("/");

    await expect(mockedPage.getByText(/biomarcadores activos/i)).toBeVisible();
    await expect(mockedPage.getByText("Producto Alpha")).toBeVisible();
    await expect(mockedPage.getByText("Producto Beta")).toBeVisible();
  });

  test("edge — empty history shows empty state message", async ({ mockedPage }) => {
    await mockBiosyncStatus(mockedPage, makeBiomarkerStatus({ has_data: false }));
    await mockScanHistory(mockedPage, []);
    await mockedPage.goto("/");

    await expect(mockedPage.getByText(/escanea tu primer producto/i)).toBeVisible();
  });

  test("edge — biomarker expiring in <30 days shows amber warning", async ({ mockedPage }) => {
    const expiresIn14Days = new Date();
    expiresIn14Days.setDate(expiresIn14Days.getDate() + 14);

    await mockBiosyncStatus(
      mockedPage,
      makeBiomarkerStatus({
        has_data: true,
        expires_at: expiresIn14Days.toISOString(),
      }),
    );
    await mockScanHistory(mockedPage, []);
    await mockedPage.goto("/");

    await expect(mockedPage.getByText(/14d/i)).toBeVisible();
  });

  test("edge — bottom nav visible on mobile viewport", async ({ mockedPage }) => {
    await mockedPage.setViewportSize({ width: 390, height: 844 });
    await mockBiosyncStatus(mockedPage, makeBiomarkerStatus({ has_data: false }));
    await mockScanHistory(mockedPage, []);
    await mockedPage.goto("/");

    await expect(mockedPage.getByRole("navigation", { name: /bottom/i })).toBeVisible();
  });

  test("edge — bottom nav hidden on desktop viewport", async ({ mockedPage }) => {
    await mockedPage.setViewportSize({ width: 1280, height: 900 });
    await mockBiosyncStatus(mockedPage, makeBiomarkerStatus({ has_data: false }));
    await mockScanHistory(mockedPage, []);
    await mockedPage.goto("/");

    await expect(mockedPage.getByRole("navigation", { name: /bottom/i })).toBeHidden();
  });
});
```

- [ ] **Step 2: Confirmar que los tests nuevos fallan (estado esperado antes de implementar)**

Desde la raíz del repo:
```bash
pnpm exec playwright test tests/specs/dashboard/ --reporter=list
```

Esperado: varios FAIL. Los tests del orbe y bottom nav fallarán porque aún no existen esos elementos. El test "happy path — populated" puede pasar si el texto "biomarcadores activos" ya existe.

- [ ] **Step 3: Commit de los tests**

```bash
git add tests/specs/dashboard/dashboard.spec.ts
git commit -m "test(dashboard): update E2E specs for home redesign — orb CTA, bottom nav, empty state"
```

---

### Task 2: Agregar keyframes y utility classes a globals.css

**Files:**
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Agregar keyframes nuevos en la sección `/* ---------- Keyframes ---------- */`**

Localizar la línea `/* ---------- Keyframes ---------- */` en `globals.css` y agregar después de los keyframes existentes (antes de `/* AvatarGlow */`):

```css
/* ── Home redesign keyframes ── */

@keyframes glow-surge {
  0%,
  100% {
    box-shadow:
      0 0 28px rgba(74, 222, 128, 0.22),
      0 0 70px rgba(74, 222, 128, 0.07);
  }
  50% {
    box-shadow:
      0 0 52px rgba(74, 222, 128, 0.48),
      0 0 110px rgba(74, 222, 128, 0.16),
      0 0 150px rgba(74, 222, 128, 0.05);
  }
}

@keyframes pulse-ring-out {
  0% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 0.45;
  }
  100% {
    transform: translate(-50%, -50%) scale(2.6);
    opacity: 0;
  }
}

@keyframes avatar-float {
  0%,
  100% {
    transform: translateY(0) scale(1);
  }
  40% {
    transform: translateY(-5px) scale(1.02);
  }
  70% {
    transform: translateY(-2px) scale(1.01);
  }
}

@keyframes float-p {
  0%,
  100% {
    transform: translateY(0) scale(1);
    opacity: 0.35;
  }
  50% {
    transform: translateY(-12px) scale(1.3);
    opacity: 0.65;
  }
}

@keyframes data-tick {
  0%,
  100% {
    opacity: 0.15;
  }
  50% {
    opacity: 0.55;
  }
}

@keyframes fade-up-kf {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes stagger-in-kf {
  from {
    opacity: 0;
    transform: translateX(-6px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
```

- [ ] **Step 2: Agregar utility classes en la sección `@layer utilities`**

Dentro del bloque `@layer utilities { ... }` existente, agregar al final:

```css
  /* Home redesign utilities */
  .animate-glow-surge {
    animation: glow-surge 2.5s ease-in-out infinite;
  }

  .animate-pulse-ring {
    animation: pulse-ring-out 2.5s ease-out infinite;
  }

  .animate-avatar-float {
    animation: avatar-float 4s ease-in-out infinite;
  }

  .animate-float-p {
    animation: float-p 3s ease-in-out infinite;
  }

  .animate-data-tick {
    animation: data-tick 1.5s ease-in-out infinite;
  }

  .animate-fade-up {
    animation: fade-up-kf 0.45s cubic-bezier(0.2, 0.8, 0.2, 1) both;
  }

  .animate-stagger-in {
    animation: stagger-in-kf 0.4s cubic-bezier(0.2, 0.8, 0.2, 1) both;
  }

  /* Orb ring — centered absolute, used in HomeOrbSection */
  .orb-ring {
    position: absolute;
    border-radius: 50%;
    top: 50%;
    left: 50%;
  }
```

- [ ] **Step 3: Verificar que el CSS compila sin errores**

```bash
cd frontend && pnpm build 2>&1 | grep -E "error|Error" | head -20
```

Esperado: sin errores CSS. Si hay errores, son de sintaxis — verificar llaves y punto y coma.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/globals.css
git commit -m "style(home): add charged animation keyframes and utility classes to globals"
```

---

### Task 3: Crear BottomNav component

**Files:**
- Create: `frontend/components/BottomNav.tsx`

- [ ] **Step 1: Crear el componente**

```typescript
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Camera, Clock, Activity } from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Home", Icon: Home },
  { href: "/scan", label: "Scan", Icon: Camera },
  { href: "/history", label: "Historial", Icon: Clock },
  { href: "/biosync", label: "Biosync", Icon: Activity },
] as const;

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="bottom navigation"
      className="fixed bottom-0 left-0 right-0 z-20 md:hidden flex items-center justify-around h-14 shrink-0"
      style={{
        background: "rgba(13,19,16,0.95)",
        borderTop: "1px solid rgba(74,222,128,0.1)",
        backdropFilter: "blur(12px)",
      }}
    >
      {NAV_ITEMS.map(({ href, label, Icon }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className="flex flex-col items-center gap-0.5 py-1 px-3 transition-opacity"
            style={{ opacity: active ? 1 : 0.4 }}
          >
            <Icon
              size={18}
              className={active ? "text-brand-green" : "text-subtext"}
              style={active ? { filter: "drop-shadow(0 0 5px rgba(74,222,128,0.6))" } : {}}
            />
            <span
              className="font-mono text-[9px] uppercase tracking-[0.06em]"
              style={{ color: active ? "var(--brand-green)" : "var(--subtext)" }}
            >
              {label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
```

- [ ] **Step 2: Verificar que TypeScript compila sin errores**

```bash
cd frontend && pnpm exec tsc --noEmit 2>&1 | grep -E "error TS" | head -20
```

Esperado: sin errores en `BottomNav.tsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/BottomNav.tsx
git commit -m "feat(home): add BottomNav component — mobile fixed bottom nav with active route"
```

---

### Task 4: Crear HomeOrbSection component

**Files:**
- Create: `frontend/components/home/HomeOrbSection.tsx`

- [ ] **Step 1: Crear directorio y componente**

```bash
mkdir -p frontend/components/home
```

```typescript
import Link from "next/link";
import Image from "next/image";

interface HomeOrbSectionProps {
  className?: string;
}

const PARTICLES = [
  { size: 3, top: "22%", left: "12%", delay: "0s", duration: "3.2s" },
  { size: 2, top: "35%", left: "85%", delay: "0.5s", duration: "2.6s" },
  { size: 3, top: "68%", left: "16%", delay: "1s", duration: "3.9s" },
  { size: 2, top: "78%", left: "80%", delay: "0.3s", duration: "2.9s" },
  { size: 2, top: "12%", left: "72%", delay: "0.7s", duration: "4.1s" },
] as const;

const DATA_LINES = ["01001101", "ADT:0.82", "E621:⚠", "USDA:OK"] as const;

export function HomeOrbSection({ className }: HomeOrbSectionProps) {
  return (
    <div className={`relative flex flex-col items-center justify-center gap-4 overflow-hidden ${className ?? ""}`}>
      {/* Scan line periódica — usa keyframe scan-line existente en globals.css */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px"
        style={{
          background: "linear-gradient(90deg, transparent, rgba(74,222,128,0.35), transparent)",
          animation: "scan-line 5s ease-in-out infinite",
        }}
      />

      {/* Partículas flotantes */}
      {PARTICLES.map((p, i) => (
        <div
          key={i}
          className="pointer-events-none absolute rounded-full animate-float-p"
          style={{
            width: p.size,
            height: p.size,
            top: p.top,
            left: p.left,
            background: "rgba(74,222,128,0.45)",
            boxShadow: "0 0 4px rgba(74,222,128,0.4)",
            animationDelay: p.delay,
            animationDuration: p.duration,
          }}
        />
      ))}

      {/* Data stream decorativo */}
      <div className="pointer-events-none absolute right-3 top-6 flex flex-col gap-0.5 font-mono text-[7px]" style={{ color: "rgba(74,222,128,0.3)" }}>
        {DATA_LINES.map((line, i) => (
          <span
            key={line}
            className="animate-data-tick"
            style={{ animationDelay: `${i * 0.3}s` }}
          >
            {line}
          </span>
        ))}
      </div>

      <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-subtext animate-fade-up">
        Toca para analizar
      </p>

      {/* Orbe — toda el área es CTA de scan */}
      <Link
        href="/scan"
        aria-label="Escanear producto"
        className="animate-fade-up relative flex items-center justify-center"
        style={{ width: 168, height: 168, animationDelay: "0.1s" }}
      >
        {/* Pulse rings */}
        <div
          className="orb-ring animate-pulse-ring"
          style={{ width: 118, height: 118, border: "1px solid rgba(74,222,128,0.3)" }}
        />
        <div
          className="orb-ring animate-pulse-ring"
          style={{ width: 118, height: 118, border: "1px solid rgba(74,222,128,0.18)", animationDelay: "0.85s" }}
        />

        {/* Ring orbital exterior (CW) */}
        <div
          className="orb-ring bs-orbital-ring-outer"
          style={{ width: 154, height: 154, border: "1px dashed rgba(74,222,128,0.14)" }}
        >
          <div
            className="absolute"
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "#4ade80",
              boxShadow: "0 0 8px rgba(74,222,128,0.9), 0 0 16px rgba(74,222,128,0.4)",
              top: -3.5,
              left: "50%",
              transform: "translateX(-50%)",
            }}
          />
        </div>

        {/* Ring orbital interior (CCW) */}
        <div
          className="orb-ring bs-orbital-ring-inner"
          style={{ width: 136, height: 136, border: "1px solid rgba(74,222,128,0.07)" }}
        >
          <div
            className="absolute"
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              background: "rgba(74,222,128,0.5)",
              boxShadow: "0 0 5px rgba(74,222,128,0.5)",
              bottom: -2.5,
              right: "18%",
            }}
          />
        </div>

        {/* Core orb con mascota */}
        <div
          className="animate-glow-surge relative z-10 flex items-center justify-center overflow-hidden"
          style={{
            width: 104,
            height: 104,
            borderRadius: "50%",
            background: "radial-gradient(circle at 38% 34%, rgba(74,222,128,0.22) 0%, rgba(74,222,128,0.03) 70%)",
            border: "1.5px solid rgba(74,222,128,0.5)",
          }}
        >
          <Image
            src="/avatars/main.png"
            alt=""
            aria-hidden
            width={78}
            height={78}
            className="animate-avatar-float object-contain"
            style={{ filter: "drop-shadow(0 0 10px rgba(74,222,128,0.5))" }}
            priority
          />
        </div>
      </Link>

      <div className="text-center animate-fade-up" style={{ animationDelay: "0.2s" }}>
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] font-bold text-brand-green">
          Escanear producto
        </p>
        <p className="font-sans text-xs text-subtext mt-0.5">Barcode · Foto · IA</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verificar TypeScript**

```bash
cd frontend && pnpm exec tsc --noEmit 2>&1 | grep -E "error TS" | head -20
```

Esperado: sin errores.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/home/HomeOrbSection.tsx
git commit -m "feat(home): add HomeOrbSection — charged orb with mascot, orbital rings, particles"
```

---

### Task 5: Crear HomeStatsPanel component

**Files:**
- Create: `frontend/components/home/HomeStatsPanel.tsx`

- [ ] **Step 1: Crear el componente**

```typescript
import Link from "next/link";
import { Activity, AlertTriangle, History, ChevronRight } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { SemaphoreBadge } from "@/components/semaphore/SemaphoreBadge";
import type { ScanHistoryEntry } from "@/lib/api/types";

interface BiosyncData {
  has_data: boolean;
  expires_at?: string;
}

interface HomeStatsPanelProps {
  biosyncData: BiosyncData | undefined;
  biosyncLoading: boolean;
  historyItems: ScanHistoryEntry[];
  historyEmpty: boolean;
  historyLoading: boolean;
}

export function HomeStatsPanel({
  biosyncData,
  biosyncLoading,
  historyItems,
  historyEmpty,
  historyLoading,
}: HomeStatsPanelProps) {
  const hasData = biosyncData?.has_data === true;
  const expiresAt = biosyncData?.expires_at;
  const daysLeft = expiresAt
    ? Math.ceil((new Date(expiresAt).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : null;
  const nearExpiry = daysLeft !== null && daysLeft < 30;

  return (
    <div className="flex flex-col gap-4 px-4 py-5 md:justify-center md:px-6">
      {/* Stats pills */}
      <div className="flex gap-3 animate-fade-up" style={{ animationDelay: "0.05s" }}>
        <div className="bs-card flex-1 px-4 py-3 text-center">
          <p className="font-mono font-bold text-2xl text-brand-green">{historyItems.length}</p>
          <p className="font-mono text-[9px] uppercase tracking-[0.06em] text-subtext mt-0.5">
            Recientes
          </p>
        </div>
        <div className="bs-card flex-1 px-4 py-3 text-center">
          {biosyncLoading ? (
            <Skeleton className="h-7 w-12 mx-auto mb-1" />
          ) : daysLeft !== null ? (
            <p className="font-mono font-bold text-2xl text-brand-amber">{daysLeft}d</p>
          ) : (
            <p className="font-mono font-bold text-2xl text-subtext">—</p>
          )}
          <p className="font-mono text-[9px] uppercase tracking-[0.06em] text-subtext mt-0.5">
            Biomarcadores
          </p>
        </div>
      </div>

      {/* Biosync card */}
      <Link
        href="/biosync"
        className="bs-card block px-4 py-3 hover:border-brand-green/30 transition-all group animate-fade-up"
        style={{ animationDelay: "0.15s" }}
      >
        {biosyncLoading ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-3 w-40" />
            <Skeleton className="h-3 w-56" />
          </div>
        ) : hasData && daysLeft !== null ? (
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Activity size={14} className="text-brand-green" />
                <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-brand-green">
                  Biomarcadores activos
                </span>
                {nearExpiry && (
                  <span
                    className="font-mono text-[9px] px-1.5 py-0.5 rounded-full"
                    style={{
                      background: "rgba(245,158,11,.12)",
                      border: "1px solid rgba(245,158,11,.3)",
                      color: "#F59E0B",
                    }}
                  >
                    <AlertTriangle size={8} className="inline mr-0.5" />
                    {daysLeft}d
                  </span>
                )}
              </div>
              <p className="font-sans text-xs text-subtext">
                Expira en {daysLeft} día{daysLeft !== 1 ? "s" : ""}
              </p>
            </div>
            <ChevronRight
              size={16}
              className="text-subtext opacity-60 group-hover:translate-x-0.5 transition-transform"
            />
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Activity size={14} className="text-subtext" />
                <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-subtext">
                  Biomarcadores
                </span>
              </div>
              <p className="font-sans text-xs text-subtext">
                Sube tu panel de sangre para alertas personalizadas
              </p>
            </div>
            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-brand-green shrink-0">
              Subir →
            </span>
          </div>
        )}
      </Link>

      {/* Historial reciente */}
      <div
        className="bs-card px-4 py-3 animate-fade-up"
        style={{ animationDelay: "0.25s" }}
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <History size={13} className="text-subtext" />
            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-subtext">
              Escaneados recientemente
            </span>
          </div>
          {!historyEmpty && (
            <Link
              href="/history"
              className="font-mono text-[10px] text-brand-green hover:opacity-70 transition-opacity"
            >
              Ver todo →
            </Link>
          )}
        </div>

        {historyLoading ? (
          <div className="flex flex-col gap-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="rounded-full shrink-0 w-8 h-8" />
                <div className="flex-1 flex flex-col gap-1.5">
                  <Skeleton className="h-3 w-3/4" />
                  <Skeleton className="h-2.5 w-1/3" />
                </div>
              </div>
            ))}
          </div>
        ) : historyEmpty ? (
          <p className="font-mono text-[10px] text-subtext py-4 text-center">
            Escanea tu primer producto para empezar.
          </p>
        ) : (
          <div className="flex flex-col">
            {historyItems.map((item, i) => (
              <HistoryRow
                key={item.id}
                item={item}
                last={i === historyItems.length - 1}
                index={i}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function HistoryRow({
  item,
  last,
  index,
}: {
  item: ScanHistoryEntry;
  last: boolean;
  index: number;
}) {
  return (
    <Link
      href={`/scan/${item.product_barcode}`}
      className="flex items-center gap-3 py-2.5 hover:bg-brand-green/[0.03] transition-colors -mx-2 px-2 rounded animate-stagger-in"
      style={{
        ...(last ? {} : { borderBottom: "1px solid rgba(74,222,128,.06)" }),
        animationDelay: `${index * 0.1}s`,
      }}
    >
      <SemaphoreBadge color={item.semaphore} size={32} />
      <div className="flex-1 min-w-0">
        <p className="font-sans text-sm text-foreground truncate">
          {item.product_name ?? item.product_barcode}
        </p>
        <p className="font-mono text-[10px] text-subtext mt-0.5">
          {relativeTime(item.scanned_at)} · {item.source === "photo" ? "Foto" : "Barcode"}
        </p>
      </div>
      <ChevronRight size={14} className="text-subtext shrink-0 opacity-60" />
    </Link>
  );
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Ahora";
  if (mins < 60) return `hace ${mins}min`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `hace ${hrs}h`;
  return `hace ${Math.floor(hrs / 24)}d`;
}
```

- [ ] **Step 2: Verificar TypeScript**

```bash
cd frontend && pnpm exec tsc --noEmit 2>&1 | grep -E "error TS" | head -20
```

Esperado: sin errores.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/home/HomeStatsPanel.tsx
git commit -m "feat(home): add HomeStatsPanel — stats pills, biosync card, staggered history"
```

---

### Task 6: Reescribir page.tsx

**Files:**
- Modify: `frontend/app/(app)/page.tsx`

- [ ] **Step 1: Reemplazar el contenido del archivo**

```typescript
"use client";

import { useQuery } from "@tanstack/react-query";
import { getBiomarkerStatus } from "@/lib/api/biosync";
import { getScanHistory } from "@/lib/api/scan";
import { HttpError } from "@/lib/api/client";
import type { ScanHistoryEntry } from "@/lib/api/types";
import { HomeOrbSection } from "@/components/home/HomeOrbSection";
import { HomeStatsPanel } from "@/components/home/HomeStatsPanel";

export default function DashboardPage() {
  const biosyncQuery = useQuery({
    queryKey: ["biosync-status"],
    queryFn: getBiomarkerStatus,
    retry: (count, err) => !(err instanceof HttpError && err.status === 404),
    staleTime: 5 * 60 * 1000,
  });

  const historyQuery = useQuery({
    queryKey: ["scan-history", 5],
    queryFn: () => getScanHistory(5),
    retry: false,
    staleTime: 60 * 1000,
  });

  const historyItems: ScanHistoryEntry[] = historyQuery.data ?? [];
  const historyEmpty = !historyQuery.isLoading && historyItems.length === 0;

  return (
    <div className="relative z-10 flex flex-col md:grid md:grid-cols-2 md:min-h-[calc(100vh-56px)]">
      <HomeOrbSection className="pt-8 pb-6 px-6 md:border-r md:border-brand-green/[0.06] md:bg-[radial-gradient(ellipse_70%_60%_at_50%_50%,rgba(74,222,128,0.04)_0%,transparent_70%)]" />
      <HomeStatsPanel
        biosyncData={biosyncQuery.data}
        biosyncLoading={biosyncQuery.isLoading}
        historyItems={historyItems}
        historyEmpty={historyEmpty}
        historyLoading={historyQuery.isLoading}
      />
    </div>
  );
}
```

- [ ] **Step 2: Verificar TypeScript**

```bash
cd frontend && pnpm exec tsc --noEmit 2>&1 | grep -E "error TS" | head -20
```

Esperado: sin errores. Si hay error en `biosyncQuery.data` (tipo desconocido), cast con `as { has_data: boolean; expires_at?: string } | undefined`.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/page.tsx
git commit -m "feat(home): rewrite dashboard — Hero Orb split panel layout"
```

---

### Task 7: Actualizar layout.tsx — agregar BottomNav

**Files:**
- Modify: `frontend/app/(app)/layout.tsx`

- [ ] **Step 1: Agregar import y componente**

Agregar import al inicio del archivo:
```typescript
import { BottomNav } from "@/components/BottomNav";
```

Modificar `<main>` para añadir padding bottom en mobile (evita que el contenido quede detrás del nav fijo):
```typescript
// antes:
<main className="flex-1 relative z-10">{children}</main>

// después:
<main className="flex-1 relative z-10 pb-14 md:pb-0">{children}</main>
```

Agregar `<BottomNav />` después de `</main>` y antes de `<SessionExpiredDialog`:
```typescript
      <main className="flex-1 relative z-10 pb-14 md:pb-0">{children}</main>
      <BottomNav />
      <SessionExpiredDialog open={sessionExpired} onConfirm={handleSessionExpiredConfirm} />
```

- [ ] **Step 2: Verificar TypeScript**

```bash
cd frontend && pnpm exec tsc --noEmit 2>&1 | grep -E "error TS" | head -20
```

Esperado: sin errores.

- [ ] **Step 3: Verificar visualmente en dev server**

```bash
cd frontend && pnpm dev
```

Abrir `http://localhost:3000` — verificar:
- Desktop (>768px): split panel visible, sin bottom nav, orbe con mascota animada
- Mobile (DevTools → 390px): orbe centrado, bottom nav visible al fondo

Detener el dev server con Ctrl+C cuando hayas verificado.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(app\)/layout.tsx
git commit -m "feat(home): add BottomNav to app layout — fixed mobile navigation"
```

---

### Task 8: Verificar que los E2E tests pasan

- [ ] **Step 1: Iniciar el stack completo (backend + frontend)**

Desde la raíz del repo:
```bash
docker compose up -d
```

O alternativamente, con los servidores ya corriendo localmente:
```bash
# Terminal 1
cd frontend && pnpm dev

# Terminal 2 (raíz del repo)
cd backend && uvicorn app.main:app --reload
```

- [ ] **Step 2: Correr los tests del dashboard**

```bash
pnpm exec playwright test tests/specs/dashboard/ --reporter=list
```

Esperado: todos los tests en verde. Si algún test falla:

- `"orb CTA links to /scan"` falla → verificar que `HomeOrbSection` renderiza `<Link href="/scan">` con `aria-label="Escanear producto"`
- `"bottom nav visible on mobile"` falla → verificar que `BottomNav` tiene `aria-label="bottom navigation"` y que el CSS `md:hidden` no lo oculta en viewport 390px
- `"bottom nav hidden on desktop"` falla → verificar que `md:hidden` funciona en viewport 1280px (Tailwind v4: clase funciona con breakpoints)
- `"empty history shows..."` falla → verificar texto exacto en `HomeStatsPanel` estado vacío

- [ ] **Step 3: Commit si hubo fixes**

```bash
git add -A
git commit -m "fix(home): address E2E test failures post-redesign"
```

---

### Task 9: Actualizar design docs

**Files:**
- Create: `docs/design/README.md`
- Modify: `docs/architecture.md`

- [ ] **Step 1: Crear docs/design/README.md**

```markdown
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
```

- [ ] **Step 2: Actualizar docs/architecture.md — sección Frontend**

Localizar la sección de Frontend en `docs/architecture.md`. Si describe la estructura de componentes, agregar:

```markdown
### Componentes — Home Dashboard

- `components/home/HomeOrbSection.tsx` — Panel izquierdo: orbe animado con mascota, CTA de scan, partículas, data stream
- `components/home/HomeStatsPanel.tsx` — Panel derecho: stats pills, biosync card, historial reciente con stagger
- `components/BottomNav.tsx` — Navegación fija inferior (mobile únicamente, `md:hidden`)
```

- [ ] **Step 3: Commit**

```bash
git add docs/design/README.md docs/architecture.md
git commit -m "docs(home): add design/README with home layout spec, update architecture component list"
```

---

### Task 10: Push y PR

- [ ] **Step 1: Verificar estado limpio**

```bash
git status
git log --oneline -10
```

Esperado: working tree limpio. Los commits deben verse en orden lógico.

- [ ] **Step 2: Push de la rama**

```bash
git push -u origin feat/home-redesign
```

- [ ] **Step 3: Abrir PR**

```bash
gh pr create \
  --title "feat(home): Hero Orb redesign — split panel, charged animations, bottom nav" \
  --base main \
  --body "$(cat <<'EOF'
## Summary

- Rewrite home dashboard con Hero Orb layout: mascota en orbe central, split panel desktop (50/50), columna en mobile
- Charged CSS-only animations: pulse rings, orbital rings CW/CCW, partículas flotantes, scan-line periódica, avatar float
- New BottomNav component — mobile fixed nav (Home / Scan / Historial / Biosync)
- New components: HomeOrbSection, HomeStatsPanel
- 7 new CSS keyframes en globals.css, prefers-reduced-motion safe
- Sin dependencias nuevas (0 nuevos paquetes)

## Test plan

- [ ] E2E: `pnpm exec playwright test tests/specs/dashboard/` — todos green
- [ ] Visual: verificar mobile 390px (orbe + bottom nav) y desktop 1280px (split panel)
- [ ] Verificar `prefers-reduced-motion` en DevTools → no animations
- [ ] Verificar estado vacío (sin historial) y estado cargando (skeletons)
- [ ] Verificar biosync card: sin datos / con datos / expirando pronto (<30d)
EOF
)"
```
