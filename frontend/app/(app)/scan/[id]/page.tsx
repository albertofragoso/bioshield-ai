"use client";

import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useEffect, useRef, useState } from "react";
import { getScanResult, scanBarcode } from "@/lib/api/scan";
import { getBiomarkerStatus } from "@/lib/api/biosync";
import type { BiomarkerStatusResponse } from "@/lib/api/types";
import Image from "next/image";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowUp,
  ArrowDown,
  HelpCircle,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  ShieldAlert,
  RotateCcw,
  Flag,
} from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { AvatarGlow } from "@/components/AvatarGlow";
import type {
  ConflictSeverity,
  IngredientConflict,
  IngredientResult,
  PersonalizedInsight,
  RegulatoryStatus,
  ScanResponse,
  SemaphoreColor,
} from "@/lib/api/types";

// ── Semáforo — config canónica (Fase B tokens) ─────────────────────────────────
type SemConfig = {
  color: string;
  Icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  avatar: string;
};
const SEMAPHORE: Record<SemaphoreColor, SemConfig> = {
  GRAY: {
    color: "#A8B3A7",
    Icon: HelpCircle,
    label: "Sin datos suficientes",
    avatar: "/avatars/gray.png",
  },
  BLUE: { color: "#60A5FA", Icon: CheckCircle, label: "Seguro", avatar: "/avatars/blue.png" },
  YELLOW: {
    color: "#FACC15",
    Icon: AlertCircle,
    label: "Precaución",
    avatar: "/avatars/yellow.png",
  },
  ORANGE: {
    color: "#FB923C",
    Icon: AlertTriangle,
    label: "Riesgo personal",
    avatar: "/avatars/orange.png",
  },
  RED: { color: "#F87171", Icon: ShieldAlert, label: "Prohibido", avatar: "/avatars/red.png" },
};

// ── Severity styles ─────────────────────────────────────────────────────────────
const SEV_STYLE: Record<ConflictSeverity, { bg: string; border: string; color: string }> = {
  HIGH: { bg: "rgba(248,113,113,.15)", border: "#F87171", color: "#F87171" },
  MEDIUM: { bg: "rgba(251,146,60,.15)", border: "#FB923C", color: "#FB923C" },
  LOW: { bg: "rgba(250,204,21,.15)", border: "#FACC15", color: "#FACC15" },
};

// ── Regulatory status styles ────────────────────────────────────────────────────
const STATUS_STYLE: Record<
  NonNullable<RegulatoryStatus>,
  { bg: string; border: string; color: string }
> = {
  Approved: { bg: "rgba(74,222,128,.12)", border: "#4ADE80", color: "#4ADE80" },
  Banned: { bg: "rgba(248,113,113,.12)", border: "#F87171", color: "#F87171" },
  Restricted: { bg: "rgba(251,146,60,.12)", border: "#FB923C", color: "#FB923C" },
  "Under Review": { bg: "rgba(250,204,21,.12)", border: "#FACC15", color: "#FACC15" },
};

// ── Sort ingredients: mayor severidad primero ──────────────────────────────────
const SEV_ORDER: Record<ConflictSeverity, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 };
function maxSevOrder(ing: IngredientResult): number {
  if (!ing.conflicts.length) return 3;
  return Math.min(...ing.conflicts.map((c) => SEV_ORDER[c.severity]));
}

// ── Tiempo relativo ─────────────────────────────────────────────────────────────
function timeAgo(iso: string): string {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `hace ${s} seg`;
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
  if (s < 86400) return `hace ${Math.floor(s / 3600)}h`;
  return new Date(iso).toLocaleDateString("es-MX");
}

// ── Explicación contextual ──────────────────────────────────────────────────────
function getExplanation(sem: SemaphoreColor, conflictCount: number): string {
  switch (sem) {
    case "BLUE":
      return "Todos los ingredientes están aprobados y no encontramos conflictos.";
    case "YELLOW":
      return `Detectamos ${conflictCount} ingrediente${conflictCount !== 1 ? "s" : ""} con restricciones o conflictos entre agencias.`;
    case "ORANGE":
      return "Este producto contiene ingredientes que pueden afectar tu perfil de biomarcadores.";
    case "RED":
      return `Contiene ${conflictCount} ingrediente${conflictCount !== 1 ? "s" : ""} prohibidos en al menos una jurisdicción.`;
    case "GRAY":
      return "No pudimos resolver suficientes ingredientes con confianza para emitir un veredicto.";
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Página principal
// ═══════════════════════════════════════════════════════════════════════════════
export default function ScanResultPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <ScanResultInner />
    </Suspense>
  );
}

function ScanResultInner() {
  const rawId = useParams<{ id: string }>().id;
  const id = decodeURIComponent(rawId);
  const isPhotoScan = id.startsWith("photo-");
  const queryClient = useQueryClient();

  const { data, isLoading, isError, isFetching } = useQuery<ScanResponse>({
    queryKey: ["scan", id],
    queryFn: () => (isPhotoScan ? getScanResult(id) : scanBarcode(id)),
    initialData: () => queryClient.getQueryData<ScanResponse>(["scan", id]),
    initialDataUpdatedAt: () => queryClient.getQueryState(["scan", id])?.dataUpdatedAt,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  const { data: bioStatus } = useQuery<BiomarkerStatusResponse>({
    queryKey: ["biomarker-status"],
    queryFn: getBiomarkerStatus,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  // Refetch once when both data and bioStatus are ready, biomarkers exist, but no insights yet.
  // Using a ref prevents re-triggering after the refetch completes.
  const hasTriggeredRefetch = useRef(false);
  useEffect(() => {
    if (
      !hasTriggeredRefetch.current &&
      data !== undefined &&
      bioStatus?.has_data === true &&
      data.personalized_insights.length === 0
    ) {
      hasTriggeredRefetch.current = true;
      queryClient.invalidateQueries({ queryKey: ["scan", id] });
    }
  }, [data, bioStatus?.has_data, id]);

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <NoCacheState />;

  const sem = SEMAPHORE[data.semaphore];
  const sortedIngredients = [...data.ingredients].sort((a, b) => maxSevOrder(a) - maxSevOrder(b));
  const conflictCount = data.ingredients.filter((i) => i.conflicts.length > 0).length;
  const explanation = getExplanation(data.semaphore, conflictCount);

  return (
    <div className="relative z-10 px-4 py-6 max-w-[1080px] mx-auto flex flex-col gap-10">
      <Link
        href="/scan"
        className="inline-flex items-center gap-1.5 font-mono text-[11px] text-subtext hover:text-foreground transition-colors uppercase tracking-[0.08em] -mb-4"
      >
        <ArrowLeft size={13} />
        escanear otro
      </Link>

      {/* ── Row 1: Hero (sticky) + Ingredientes ── */}
      <div className="lg:grid lg:grid-cols-[300px_1fr] lg:gap-10 lg:items-start">
        {/* Columna izquierda: hero + meta */}
        <div className="lg:sticky lg:top-[78px] flex flex-col gap-5 mb-8 lg:mb-0">
          {/* Hero card */}
          <div
            className="bs-card px-6 py-7 flex flex-col items-center gap-4 relative overflow-hidden"
            style={{ borderColor: `rgba(${hexToRgb(sem.color)}, .35)` }}
          >
            <div
              className="absolute left-1/2 -translate-x-1/2 top-0 pointer-events-none"
              style={{
                width: "200px",
                height: "80px",
                background: `radial-gradient(ellipse, ${sem.color}20 0%, transparent 70%)`,
              }}
            />
            <div
              className="flex justify-center animate-pulse"
              aria-live="polite"
              aria-label={`Semáforo: ${sem.label}`}
              style={{ filter: `drop-shadow(0 0 20px ${sem.color}70)` }}
            >
              <Image
                src={sem.avatar}
                alt=""
                aria-hidden
                width={120}
                height={120}
                className="object-contain"
                priority
              />
            </div>
            <div className="flex flex-col items-center gap-1.5 text-center">
              <h1
                className="font-sans font-bold text-2xl flex items-center gap-2"
                style={{ color: sem.color }}
              >
                <sem.Icon size={22} />
                {sem.label}
              </h1>
              <p className="font-sans text-sm text-foreground">
                {data.product_name ?? "Producto sin nombre"}
              </p>
              <p className="font-mono text-[11px] text-subtext tracking-[0.06em]">
                {data.product_barcode}
              </p>
              {data.conflict_severity && (
                <span
                  className="mt-1 px-2 py-0.5 rounded-full font-mono text-[10px] uppercase tracking-[0.1em]"
                  style={{
                    background: SEV_STYLE[data.conflict_severity].bg,
                    border: `1px solid ${SEV_STYLE[data.conflict_severity].border}`,
                    color: SEV_STYLE[data.conflict_severity].color,
                  }}
                >
                  {data.conflict_severity} severity
                </span>
              )}
            </div>
          </div>

          {/* Explicación contextual */}
          <p className="font-sans text-sm text-foreground/80 leading-relaxed px-1 text-center">
            {explanation}
          </p>

          {/* Metadata + acciones */}
          <div className="flex flex-col items-center gap-3 pt-1">
            <p className="font-mono text-[10px] text-subtext">
              Escaneado vía {data.source === "barcode" ? "código de barras" : "foto"} ·{" "}
              {timeAgo(data.scanned_at)}
            </p>
            <div className="flex gap-2">
              <Link
                href="/scan"
                className="flex items-center gap-1.5 px-4 py-2.5 rounded-button font-mono text-[12px] uppercase tracking-[0.08em] text-brand-green transition-all bs-glow-green hover:bs-glow-green-strong"
                style={{
                  background: "rgba(74,222,128,.12)",
                  border: "1px solid rgba(74,222,128,.3)",
                }}
              >
                <RotateCcw size={13} />
                Escanear otro
              </Link>
              <button
                disabled
                title="Próximamente"
                className="flex items-center gap-1.5 px-4 py-2.5 rounded-button font-mono text-[12px] uppercase tracking-[0.08em] text-subtext opacity-40 cursor-not-allowed"
                style={{ border: "1px solid rgba(74,222,128,.15)" }}
              >
                <Flag size={13} />
                Reportar
              </button>
            </div>
          </div>
        </div>

        {/* Columna derecha: ingredientes */}
        <div>
          <h2 className="font-mono text-[11px] text-subtext uppercase tracking-[0.1em] mb-4">
            {sortedIngredients.length} ingrediente{sortedIngredients.length !== 1 ? "s" : ""}{" "}
            analizados
          </h2>
          {sortedIngredients.length === 0 ? (
            <div className="bs-card px-6 py-8 text-center">
              <p className="font-sans text-sm text-subtext">
                No identificamos ingredientes en la etiqueta.
              </p>
              <p className="font-mono text-[11px] text-subtext/60 mt-2">
                Intenta con una foto más nítida o mejor iluminada.
              </p>
            </div>
          ) : (
            <Accordion multiple className="flex flex-col gap-0">
              {sortedIngredients.map((ing, i) => (
                <IngredientItem key={`${ing.name}-${i}`} ingredient={ing} index={i} />
              ))}
            </Accordion>
          )}
        </div>
      </div>

      {/* ── Row 2: Para Ti — fila dedicada ── */}
      <div className="pt-2" style={{ borderTop: "1px solid rgba(74,222,128,.08)" }}>
        {data.personalized_insights.length > 0 ? (
          <ParaTiSection insights={data.personalized_insights} />
        ) : !bioStatus?.has_data ? (
          <div className="max-w-[480px]">
            <BiomarkerEmptyState />
          </div>
        ) : isFetching ? null : (
          <BiomarkerClearState />
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Sub-componentes inline (on-demand — único consumer por ahora)
// ═══════════════════════════════════════════════════════════════════════════════

function IngredientItem({
  ingredient: ing,
  index,
}: {
  ingredient: IngredientResult;
  index: number;
}) {
  const statusStyle = ing.regulatory_status ? STATUS_STYLE[ing.regulatory_status] : null;
  const confidence = Math.round(ing.confidence_score * 100);

  return (
    <AccordionItem
      value={`ing-${index}`}
      className="border-0"
      style={{ borderBottom: "1px solid rgba(74,222,128,.08)" }}
    >
      <AccordionTrigger className="py-4 px-2 hover:no-underline hover:bg-[rgba(74,222,128,.03)] rounded-[6px] transition-colors">
        <div className="flex flex-1 items-center gap-3 min-w-0 mr-3">
          {/* Nombre */}
          <span className="font-sans text-sm text-foreground truncate min-w-0">{ing.name}</span>

          {/* Status badge */}
          {statusStyle && ing.regulatory_status && (
            <span
              className="shrink-0 px-1.5 py-0.5 rounded-full font-mono text-[9px] uppercase tracking-[0.08em]"
              style={{
                background: statusStyle.bg,
                border: `1px solid ${statusStyle.border}`,
                color: statusStyle.color,
              }}
            >
              {ing.regulatory_status}
            </span>
          )}

          {/* Conflicts badge */}
          {ing.conflicts.length > 0 && (
            <span
              className="shrink-0 px-1.5 py-0.5 rounded-full font-mono text-[9px] uppercase tracking-[0.08em]"
              style={{
                background: SEV_STYLE[ing.conflicts[0].severity].bg,
                border: `1px solid ${SEV_STYLE[ing.conflicts[0].severity].border}`,
                color: SEV_STYLE[ing.conflicts[0].severity].color,
              }}
            >
              {ing.conflicts.length} conflicto{ing.conflicts.length !== 1 ? "s" : ""}
            </span>
          )}

          {/* Confidence bar */}
          <div className="shrink-0 flex items-center gap-1.5 ml-auto">
            <div
              className="w-14 h-[3px] rounded-full overflow-hidden"
              style={{ background: "rgba(74,222,128,.1)" }}
            >
              <div
                className="h-full rounded-full"
                style={{
                  width: `${confidence}%`,
                  background:
                    confidence >= 80 ? "#4ADE80" : confidence >= 50 ? "#FB923C" : "#F87171",
                }}
              />
            </div>
            <span className="font-mono text-[9px] text-subtext">{confidence}%</span>
          </div>
        </div>
      </AccordionTrigger>

      <AccordionContent className="px-2 pb-4">
        <div className="flex flex-col gap-4">
          {/* Identificadores */}
          <div className="flex flex-wrap gap-4">
            {ing.cas_number && (
              <div>
                <p className="font-mono text-[9px] text-subtext uppercase tracking-[0.08em] mb-0.5">
                  CAS
                </p>
                <p className="font-mono text-[12px] text-foreground">{ing.cas_number}</p>
              </div>
            )}
            {ing.e_number && (
              <div>
                <p className="font-mono text-[9px] text-subtext uppercase tracking-[0.08em] mb-0.5">
                  E-number
                </p>
                <p className="font-mono text-[12px] text-foreground">{ing.e_number}</p>
              </div>
            )}
            {ing.canonical_name && ing.canonical_name !== ing.name && (
              <div>
                <p className="font-mono text-[9px] text-subtext uppercase tracking-[0.08em] mb-0.5">
                  Nombre canónico
                </p>
                <p className="font-sans text-[12px] text-foreground">{ing.canonical_name}</p>
              </div>
            )}
          </div>

          {/* Conflictos */}
          {ing.conflicts.length > 0 && (
            <div className="flex flex-col gap-2">
              {ing.conflicts.map((conflict, ci) => (
                <ConflictRow key={ci} conflict={conflict} />
              ))}
            </div>
          )}
        </div>
      </AccordionContent>
    </AccordionItem>
  );
}

function ConflictRow({ conflict }: { conflict: IngredientConflict }) {
  const style = SEV_STYLE[conflict.severity];
  return (
    <div
      className="rounded-input px-3 py-3 flex flex-col gap-2"
      style={{ background: style.bg, border: `1px solid ${style.border}40` }}
    >
      {/* Header */}
      <div className="flex items-center gap-2">
        <span
          className="px-1.5 py-0.5 rounded-full font-mono text-[9px] uppercase tracking-[0.08em]"
          style={{
            background: `${style.border}25`,
            border: `1px solid ${style.border}`,
            color: style.color,
          }}
        >
          {conflict.severity}
        </span>
        <span className="font-mono text-[9px] text-subtext uppercase tracking-[0.06em]">
          {conflict.conflict_type}
        </span>
      </div>

      {/* Summary */}
      <p className="font-sans text-[12px] text-foreground leading-[1.5]">{conflict.summary}</p>

      {/* Sources */}
      {conflict.sources.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {conflict.sources.map((src) => (
            <span
              key={src}
              className="px-2 py-0.5 rounded-full font-mono text-[9px] text-subtext"
              style={{
                background: "rgba(74,222,128,.06)",
                border: "1px solid rgba(74,222,128,.12)",
              }}
            >
              {src}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Para ti — color map ────────────────────────────────────────────────────────

const INSIGHT_BORDER: Record<string, string> = {
  red: "#F87171",
  orange: "#FB923C",
  yellow: "#FACC15",
};

// ── Para ti — section ────────────────────────────────────────────────────────

function ParaTiSection({ insights }: { insights: PersonalizedInsight[] }) {
  const alerts = insights.filter((i) => i.kind === "alert");
  const watches = insights.filter((i) => i.kind === "watch");
  const initialTab: "alerts" | "watches" = alerts.length > 0 ? "alerts" : "watches";
  const [tab, setTab] = useState<"alerts" | "watches">(initialTab);
  const [index, setIndex] = useState(0);
  const trackRef = useRef<HTMLDivElement>(null);

  const active = tab === "alerts" ? alerts : watches;

  function scrollToIndex(i: number) {
    setIndex(i);
    const track = trackRef.current;
    if (!track) return;
    const card = track.children[i] as HTMLElement | undefined;
    if (card) track.scrollTo({ left: card.offsetLeft, behavior: "smooth" });
  }

  function handleTabChange(t: "alerts" | "watches") {
    setTab(t);
    setIndex(0);
    if (trackRef.current) trackRef.current.scrollTo({ left: 0, behavior: "smooth" });
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Header: título izq, tabs der */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="font-sans font-semibold text-base text-foreground">Para ti</h2>
          <p className="font-mono text-[10px] text-subtext uppercase tracking-[0.06em] mt-0.5">
            Cruce con tus biomarcadores recientes
          </p>
        </div>
        <div className="sm:w-64 shrink-0">
          <ParaTiTabs
            tab={tab}
            onChange={handleTabChange}
            alertCount={alerts.length}
            watchCount={watches.length}
          />
        </div>
      </div>

      {tab === "watches" && (
        <p className="font-sans text-[12px] text-foreground/55 leading-[1.5] -mt-2">
          Estos marcadores están en rango, pero este producto los podría mover.
        </p>
      )}

      {/* Carousel — scroll-snap, peek del siguiente card visible */}
      <div
        ref={trackRef}
        className="flex gap-4 overflow-x-auto snap-x snap-mandatory"
        style={{ scrollbarWidth: "none", WebkitOverflowScrolling: "touch" } as React.CSSProperties}
      >
        {active.map((insight, i) => (
          <div key={i} className="w-full sm:w-[460px] shrink-0 snap-start">
            <DiagnosticInsightCard insight={insight} index={i} />
          </div>
        ))}
      </div>

      {/* Dots */}
      {active.length > 1 && (
        <div className="flex items-center gap-1.5">
          {active.map((_, i) => (
            <button
              key={i}
              onClick={() => scrollToIndex(i)}
              aria-label={`Ir al insight ${i + 1}`}
              className="rounded-full transition-all duration-200"
              style={{
                width: i === index ? "16px" : "6px",
                height: "6px",
                background: i === index ? "#4ADE80" : "rgba(74,222,128,.22)",
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ParaTiTabs({
  tab,
  onChange,
  alertCount,
  watchCount,
}: {
  tab: "alerts" | "watches";
  onChange: (t: "alerts" | "watches") => void;
  alertCount: number;
  watchCount: number;
}) {
  const Pill = ({
    active,
    id,
    label,
    count,
    color,
  }: {
    active: boolean;
    id: "alerts" | "watches";
    label: string;
    count: number;
    color: string;
  }) => {
    const rgb = hexToRgb(color);
    const isEmpty = count === 0;
    return (
      <button
        onClick={() => !isEmpty && onChange(id)}
        disabled={isEmpty}
        className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-card font-mono text-[11px] uppercase tracking-[0.08em] transition-all disabled:cursor-not-allowed"
        style={{
          background: active && !isEmpty ? `rgba(${rgb}, .09)` : "transparent",
          border: `1px solid rgba(${rgb}, ${active && !isEmpty ? 0.4 : 0.1})`,
          color: active && !isEmpty ? color : "rgba(255,255,255,.25)",
          boxShadow: active && !isEmpty ? `0 0 20px rgba(${rgb}, .12)` : "none",
          opacity: isEmpty ? 0.45 : 1,
        }}
      >
        <span
          className="w-1.5 h-1.5 rounded-full"
          style={{ background: color, opacity: active && !isEmpty ? 1 : 0.2 }}
        />
        {label} <span className="opacity-55">({count})</span>
      </button>
    );
  };

  return (
    <div className="flex gap-2">
      <Pill
        active={tab === "alerts"}
        id="alerts"
        label="Alertas"
        count={alertCount}
        color="#FB923C"
      />
      <Pill
        active={tab === "watches"}
        id="watches"
        label="Vigilar"
        count={watchCount}
        color="#FACC15"
      />
    </div>
  );
}

// ── Diagnostic insight card ───────────────────────────────────────────────────

function StatusPill({
  classification,
  kind,
  color,
}: {
  classification: string;
  kind: string;
  color: string;
}) {
  const label = kind === "watch" ? "NORMAL" : classification === "high" ? "ALTO" : "BAJO";
  const rgb = hexToRgb(color);
  return (
    <span
      className="px-2.5 py-1 rounded-full font-mono text-[9px] uppercase tracking-[0.1em] font-medium whitespace-nowrap"
      style={{
        background: `rgba(${rgb}, .12)`,
        border: `1px solid rgba(${rgb}, .38)`,
        color,
      }}
    >
      {label}
    </span>
  );
}

function ImpactArrows({
  direction,
  severity,
}: {
  direction: "raises" | "lowers";
  severity: PersonalizedInsight["severity"];
}) {
  const count = severity === "HIGH" ? 3 : severity === "MEDIUM" ? 2 : 1;
  const color = severity === "HIGH" ? "#F87171" : severity === "MEDIUM" ? "#FB923C" : "#FACC15";
  const Icon = direction === "raises" ? ArrowUp : ArrowDown;
  return (
    <span className="flex items-center" style={{ color }}>
      {Array.from({ length: count }).map((_, i) => (
        <Icon key={i} size={13} strokeWidth={2.5} style={{ marginLeft: i === 0 ? 0 : -4 }} />
      ))}
    </span>
  );
}

function BiomarkerRangeBar({
  insight,
  accent,
  animDelay = 0,
}: {
  insight: PersonalizedInsight;
  accent: string;
  animDelay?: number;
}) {
  const { biomarker_value: value, reference_range_low: lo, reference_range_high: hi } = insight;

  if (lo == null && hi == null) return null;

  // Extend display window 30% beyond range so the marker stays visible even when out-of-range
  const span = (hi ?? value * 1.5) - (lo ?? 0);
  const minVal = (lo ?? 0) - span * 0.3;
  const maxVal = (hi ?? value * 1.5) + span * 0.3;
  const total = maxVal - minVal;

  const pct = (n: number) => Math.max(0, Math.min(100, ((n - minVal) / total) * 100));

  const lowEnd = lo != null ? pct(lo) : 0;
  const highStart = hi != null ? pct(hi) : 100;
  const markerPct = pct(value);

  // Marker appears ~70% into the bar fill animation
  const markerDelay = animDelay + 630;
  // Glow/ring start after the marker has fully appeared
  const glowDelay = markerDelay + 300;

  return (
    <div className="flex flex-col gap-2 w-full">
      {/* Track area — position context for animated zones + marker layers */}
      <div className="relative h-2">
        {/* ── Animated zones (clip-path reveal, no child distortion) ── */}
        <div
          className="absolute inset-0 rounded-full overflow-hidden animate-range-fill"
          style={{ animationDelay: `${animDelay}ms` }}
        >
          {/* Base track */}
          <div className="absolute inset-0 bg-foreground/[0.07]" />
          {/* Low zone */}
          {lo != null && (
            <div
              className="absolute inset-y-0 left-0"
              style={{
                width: `${lowEnd}%`,
                background: "linear-gradient(90deg, rgba(96,165,250,.16), rgba(96,165,250,.30))",
              }}
            />
          )}
          {/* Normal zone */}
          <div
            className="absolute inset-y-0"
            style={{
              left: `${lowEnd}%`,
              width: `${highStart - lowEnd}%`,
              background: "linear-gradient(90deg, rgba(74,222,128,.24), rgba(74,222,128,.32))",
            }}
          />
          {/* High zone */}
          {hi != null && (
            <div
              className="absolute inset-y-0"
              style={{
                left: `${highStart}%`,
                right: 0,
                background: "linear-gradient(90deg, rgba(248,113,113,.30), rgba(248,113,113,.16))",
              }}
            />
          )}
        </div>

        {/* ── Marker layers (outside the clipped zones div) ── */}

        {/* Halo — blurred background pulse */}
        <div
          className="absolute top-1/2 w-4 h-4 rounded-full animate-marker-halo"
          style={{
            left: `calc(${markerPct}% - 8px)`,
            background: accent,
            filter: "blur(5px)",
            animationDelay: `${glowDelay}ms`,
          }}
        />

        {/* Ring — expanding border */}
        <div
          className="absolute top-1/2 w-3 h-3 rounded-full animate-marker-ring"
          style={{
            left: `calc(${markerPct}% - 6px)`,
            border: `1.5px solid ${accent}`,
            animationDelay: `${glowDelay + 400}ms`,
          }}
        />

        {/* Marker dot */}
        <div
          className="absolute top-1/2 w-3 h-3 rounded-full z-10 animate-marker-appear"
          style={{
            left: `calc(${markerPct}% - 6px)`,
            background: accent,
            boxShadow: `0 0 8px ${accent}, 0 0 0 2px rgba(8,12,7,.95)`,
            animationDelay: `${markerDelay}ms`,
          }}
        />
      </div>

      {/* Range labels */}
      <div className="flex justify-between font-mono text-[9px] text-subtext uppercase tracking-[0.04em]">
        <span>{lo ?? ""}</span>
        <span className="opacity-40">{insight.biomarker_unit}</span>
        <span>{hi ?? ""}</span>
      </div>
    </div>
  );
}

function DiagnosticInsightCard({
  insight,
  index,
}: {
  insight: PersonalizedInsight;
  index: number;
}) {
  const accent = INSIGHT_BORDER[insight.avatar_variant] ?? "#6B8A6A";
  const rgb = hexToRgb(accent);
  const base = index * 60;
  const row = (i: number): React.CSSProperties => ({
    animationDelay: `${base + i * 80}ms`,
  });

  const impactVerb = insight.kind === "watch" ? "podría moverlo" : "lo movería";

  return (
    <article
      className="relative overflow-hidden rounded-card px-5 py-5 flex flex-col gap-4 h-full"
      style={{
        background: `rgba(${rgb}, .04)`,
        border: `1px solid rgba(${rgb}, .28)`,
        boxShadow: `0 0 32px rgba(${rgb}, .12), inset 0 0 60px rgba(${rgb}, .03)`,
      }}
    >
      {/* Corner accents */}
      <span className="bs-corner bs-corner-tl" style={{ borderColor: `rgba(${rgb}, .5)` }} />
      <span className="bs-corner bs-corner-br" style={{ borderColor: `rgba(${rgb}, .5)` }} />

      {/* Row 0 — avatar + label + status pill */}
      <header className="flex items-center gap-3 animate-data-row-in" style={row(0)}>
        <AvatarGlow variant={insight.avatar_variant} size={56} intensity="soft" />
        <div className="flex-1 min-w-0">
          <p className="font-mono text-[9px] uppercase tracking-[0.08em] text-subtext">
            Tu marcador
          </p>
          <h3
            className="font-sans font-semibold text-[13px] leading-tight mt-0.5 truncate"
            style={{ color: accent }}
          >
            {insight.friendly_biomarker_label}
          </h3>
        </div>
        <StatusPill classification={insight.classification} kind={insight.kind} color={accent} />
      </header>

      {/* Row 1 — numeric value */}
      <div className="animate-data-row-in flex items-baseline gap-1.5" style={row(1)}>
        <span className="font-mono text-[30px] font-medium text-foreground leading-none">
          {insight.biomarker_value}
        </span>
        <span className="font-mono text-[12px] text-subtext">{insight.biomarker_unit}</span>
      </div>

      {/* Row 2 — range bar */}
      <div className="animate-data-row-in" style={row(2)}>
        <BiomarkerRangeBar insight={insight} accent={accent} animDelay={base + 2 * 80} />
      </div>

      {/* Row 3 — impact direction */}
      <div className="animate-data-row-in flex items-center gap-2" style={row(3)}>
        <span className="font-mono text-[10px] uppercase tracking-[0.07em] text-subtext">
          Este producto {impactVerb}
        </span>
        <ImpactArrows direction={insight.impact_direction} severity={insight.severity} />
      </div>

      {/* Row 4 — explanation + recommendation */}
      <div className="animate-data-row-in flex flex-col gap-1.5" style={row(4)}>
        <p className="font-sans text-[13px] text-foreground/85 leading-[1.55]">
          {insight.friendly_explanation}
        </p>
        <p
          className="font-sans text-[12px] leading-[1.5] flex gap-1.5"
          style={{ color: "#6B8A6A" }}
        >
          <span aria-hidden>→</span>
          <span>{insight.friendly_recommendation}</span>
        </p>
      </div>

      {/* Row 5 — ingredient pills */}
      {insight.affecting_ingredients.length > 0 && (
        <div className="animate-data-row-in flex flex-wrap gap-1.5" style={row(5)}>
          {insight.affecting_ingredients.map((ingr) => (
            <span
              key={ingr}
              className="px-2 py-0.5 rounded-full font-mono text-[10px] uppercase tracking-[0.04em]"
              style={{
                background: `rgba(${rgb}, .09)`,
                border: `1px solid rgba(${rgb}, .28)`,
                color: accent,
              }}
            >
              {ingr}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}

function BiomarkerEmptyState() {
  return (
    <div
      className="rounded-card px-4 py-4 flex flex-col items-center gap-2 text-center"
      style={{ background: "rgba(74,222,128,.03)", border: "1px solid rgba(74,222,128,.1)" }}
    >
      <p className="font-sans text-[13px] text-foreground/80 leading-[1.5]">
        Sube tus biomarcadores para que cada scan se adapte a ti.
      </p>
      <Link
        href="/biosync"
        className="font-mono text-[11px] text-brand-green hover:opacity-70 transition-opacity uppercase tracking-[0.06em]"
      >
        Ir a Biosync →
      </Link>
    </div>
  );
}

function BiomarkerClearState() {
  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2 className="font-sans font-semibold text-base text-foreground">Para ti</h2>
        <p className="font-mono text-[10px] text-subtext uppercase tracking-[0.06em] mt-0.5">
          Basado en tus biomarcadores recientes
        </p>
      </div>
      <div
        className="w-full rounded-card py-10 flex flex-col items-center justify-center gap-4 relative overflow-hidden"
        style={{
          background: "rgba(96,165,250,.05)",
          border: "1px solid rgba(96,165,250,.35)",
          boxShadow: "0 0 32px rgba(96,165,250,.18), inset 0 0 40px rgba(96,165,250,.04)",
        }}
      >
        <div
          className="absolute left-1/2 -translate-x-1/2 top-0 pointer-events-none"
          style={{
            width: "320px",
            height: "80px",
            background: "radial-gradient(ellipse, rgba(96,165,250,.18) 0%, transparent 70%)",
          }}
        />
        <Image
          src="/avatars/success.png"
          alt=""
          aria-hidden
          width={130}
          height={130}
          className="object-contain animate-pulse-glow relative z-10"
          style={{ filter: "drop-shadow(0 0 39px rgba(96,165,250,0.25))" }}
        />
        <p className="font-sans text-[14px] text-foreground/80 leading-[1.5] text-center max-w-[400px]">
          Ningún ingrediente de este producto presenta conflictos con tus biomarcadores.
        </p>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="relative z-10 flex flex-col items-center justify-center min-h-[calc(100vh-56px)] gap-5 px-4">
      <div className="bs-mascot-glow">
        <Image
          src="/avatars/progress.png"
          alt=""
          aria-hidden
          width={100}
          height={100}
          className="object-contain animate-pulse-glow"
          priority
        />
      </div>
      <div className="text-center">
        <p className="font-sans text-sm text-foreground">Analizando producto...</p>
        <p className="font-mono text-[11px] text-subtext mt-1 uppercase tracking-[0.08em]">
          unos segundos
        </p>
      </div>
    </div>
  );
}

function NoCacheState() {
  return (
    <div className="relative z-10 flex flex-col items-center justify-center min-h-[calc(100vh-56px)] gap-5 px-4">
      <p className="font-sans text-base text-foreground font-semibold">Sin datos para mostrar</p>
      <p className="font-mono text-[12px] text-subtext text-center max-w-[280px] leading-[1.6]">
        Escanea un producto para ver su análisis detallado.
      </p>
      <Link
        href="/scan"
        className="px-6 py-3 rounded-button font-mono text-[12px] uppercase tracking-[0.08em] text-brand-green bs-glow-green"
        style={{ background: "rgba(74,222,128,.12)", border: "1px solid rgba(74,222,128,.3)" }}
      >
        ⟶ escanear producto
      </Link>
    </div>
  );
}

// Convierte un color HEX #RRGGBB a "R,G,B" para usar en rgba()
function hexToRgb(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `${r},${g},${b}`;
}
