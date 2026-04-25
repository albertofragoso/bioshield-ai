"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense } from "react";
import { scanBarcode } from "@/lib/api/scan";
import Image from "next/image";
import Link from "next/link";
import {
  ArrowLeft,
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
import type {
  ConflictSeverity,
  IngredientConflict,
  IngredientResult,
  RegulatoryStatus,
  ScanResponse,
  SemaphoreColor,
} from "@/lib/api/types";

// ── Semáforo — config canónica (Fase B tokens) ─────────────────────────────────
type SemConfig = { color: string; Icon: React.ComponentType<{ size?: number; className?: string }>; label: string; avatar: string };
const SEMAPHORE: Record<SemaphoreColor, SemConfig> = {
  GRAY:   { color: "#A8B3A7", Icon: HelpCircle,    label: "Sin datos suficientes", avatar: "/avatars/gray.png"   },
  BLUE:   { color: "#60A5FA", Icon: CheckCircle,   label: "Seguro",                avatar: "/avatars/blue.png"   },
  YELLOW: { color: "#FACC15", Icon: AlertCircle,   label: "Precaución",            avatar: "/avatars/yellow.png" },
  ORANGE: { color: "#FB923C", Icon: AlertTriangle, label: "Riesgo personal",       avatar: "/avatars/orange.png" },
  RED:    { color: "#F87171", Icon: ShieldAlert,   label: "Prohibido",             avatar: "/avatars/red.png"    },
};

// ── Severity styles ─────────────────────────────────────────────────────────────
const SEV_STYLE: Record<ConflictSeverity, { bg: string; border: string; color: string }> = {
  HIGH:   { bg: "rgba(248,113,113,.15)", border: "#F87171", color: "#F87171" },
  MEDIUM: { bg: "rgba(251,146,60,.15)",  border: "#FB923C", color: "#FB923C" },
  LOW:    { bg: "rgba(250,204,21,.15)",  border: "#FACC15", color: "#FACC15" },
};

// ── Regulatory status styles ────────────────────────────────────────────────────
const STATUS_STYLE: Record<NonNullable<RegulatoryStatus>, { bg: string; border: string; color: string }> = {
  Approved:       { bg: "rgba(74,222,128,.12)",  border: "#4ADE80", color: "#4ADE80"  },
  Banned:         { bg: "rgba(248,113,113,.12)", border: "#F87171", color: "#F87171"  },
  Restricted:     { bg: "rgba(251,146,60,.12)",  border: "#FB923C", color: "#FB923C"  },
  "Under Review": { bg: "rgba(250,204,21,.12)",  border: "#FACC15", color: "#FACC15"  },
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
  if (s < 60)    return `hace ${s} seg`;
  if (s < 3600)  return `hace ${Math.floor(s / 60)} min`;
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
  const id = decodeURIComponent(rawId); // normalize regardless of how Next.js encodes the path segment
  const searchParams = useSearchParams();
  const viaPhoto = searchParams.get("via") === "photo";
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery<ScanResponse>({
    queryKey: ["scan", id],
    queryFn: () => scanBarcode(id),
    enabled: !viaPhoto,
    initialData: () => queryClient.getQueryData<ScanResponse>(["scan", id]),
    initialDataUpdatedAt: () => queryClient.getQueryState(["scan", id])?.dataUpdatedAt,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return viaPhoto ? <PhotoExpiredState /> : <NoCacheState />;

  const sem = SEMAPHORE[data.semaphore];
  const sortedIngredients = [...data.ingredients].sort(
    (a, b) => maxSevOrder(a) - maxSevOrder(b),
  );
  const conflictCount = data.ingredients.filter((i) => i.conflicts.length > 0).length;
  const explanation = getExplanation(data.semaphore, conflictCount);

  return (
    <div className="relative z-10 px-4 py-6 max-w-[1080px] mx-auto">
      <Link
        href="/scan"
        className="inline-flex items-center gap-1.5 font-mono text-[11px] text-subtext hover:text-foreground transition-colors uppercase tracking-[0.08em] mb-6"
      >
        <ArrowLeft size={13} />
        escanear otro
      </Link>

      {/* Layout 2 columnas en desktop */}
      <div className="lg:grid lg:grid-cols-[380px_1fr] lg:gap-10 lg:items-start">

        {/* ── Columna izquierda: hero + meta ── */}
        <div className="lg:sticky lg:top-[78px] flex flex-col gap-5 mb-8 lg:mb-0">

          {/* Hero card */}
          <div
            className="bs-card px-6 py-7 flex flex-col items-center gap-4 relative overflow-hidden"
            style={{ borderColor: `rgba(${hexToRgb(sem.color)}, .35)` }}
          >
            {/* Glow superior del color del semáforo */}
            <div
              className="absolute left-1/2 -translate-x-1/2 top-0 pointer-events-none"
              style={{
                width: "200px",
                height: "80px",
                background: `radial-gradient(ellipse, ${sem.color}20 0%, transparent 70%)`,
              }}
            />

            {/* Avatar con glow dinámico del color del semáforo */}
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
                width={130}
                height={130}
                className="object-contain"
                priority
              />
            </div>

            {/* Texto del hero — centrado */}
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

          {/* Alerta de biomarcadores — solo si ORANGE */}
          {data.semaphore === "ORANGE" && <BiomarkerAlert />}

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
                style={{ background: "rgba(74,222,128,.12)", border: "1px solid rgba(74,222,128,.3)" }}
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

        {/* ── Columna derecha: ingredientes ── */}
        <div>
          <h2 className="font-mono text-[11px] text-subtext uppercase tracking-[0.1em] mb-4">
            {sortedIngredients.length} ingrediente{sortedIngredients.length !== 1 ? "s" : ""} analizados
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
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Sub-componentes inline (on-demand — único consumer por ahora)
// ═══════════════════════════════════════════════════════════════════════════════

function IngredientItem({ ingredient: ing, index }: { ingredient: IngredientResult; index: number }) {
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
          <span className="font-sans text-sm text-foreground truncate min-w-0">
            {ing.name}
          </span>

          {/* Status badge */}
          {statusStyle && ing.regulatory_status && (
            <span
              className="shrink-0 px-1.5 py-0.5 rounded-full font-mono text-[9px] uppercase tracking-[0.08em]"
              style={{ background: statusStyle.bg, border: `1px solid ${statusStyle.border}`, color: statusStyle.color }}
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
                  background: confidence >= 80 ? "#4ADE80" : confidence >= 50 ? "#FB923C" : "#F87171",
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
                <p className="font-mono text-[9px] text-subtext uppercase tracking-[0.08em] mb-0.5">CAS</p>
                <p className="font-mono text-[12px] text-foreground">{ing.cas_number}</p>
              </div>
            )}
            {ing.e_number && (
              <div>
                <p className="font-mono text-[9px] text-subtext uppercase tracking-[0.08em] mb-0.5">E-number</p>
                <p className="font-mono text-[12px] text-foreground">{ing.e_number}</p>
              </div>
            )}
            {ing.canonical_name && ing.canonical_name !== ing.name && (
              <div>
                <p className="font-mono text-[9px] text-subtext uppercase tracking-[0.08em] mb-0.5">Nombre canónico</p>
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
          style={{ background: `${style.border}25`, border: `1px solid ${style.border}`, color: style.color }}
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
              style={{ background: "rgba(74,222,128,.06)", border: "1px solid rgba(74,222,128,.12)" }}
            >
              {src}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function BiomarkerAlert() {
  return (
    <div
      className="rounded-card px-4 py-4 flex flex-col gap-1.5"
      style={{
        background: "rgba(251,146,60,.06)",
        border: "1px solid rgba(251,146,60,.35)",
      }}
    >
      <div className="flex items-center gap-2">
        <AlertTriangle size={14} style={{ color: "#FB923C" }} />
        <p className="font-mono text-[11px] uppercase tracking-[0.08em]" style={{ color: "#FB923C" }}>
          Alerta de biomarcadores
        </p>
      </div>
      <p className="font-sans text-[12px] text-foreground/80 leading-[1.5]">
        Este producto contiene ingredientes que podrían afectar tu perfil metabólico.
        Sube tu panel de sangre en{" "}
        <Link href="/biosync" className="underline text-brand-teal">
          biosync
        </Link>{" "}
        para alertas personalizadas.
      </p>
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

function PhotoExpiredState() {
  return (
    <div className="relative z-10 flex flex-col items-center justify-center min-h-[calc(100vh-56px)] gap-5 px-4 text-center">
      <div className="bs-mascot-glow">
        <Image
          src="/avatars/support.png"
          alt=""
          aria-hidden
          width={100}
          height={100}
          className="object-contain animate-pulse-glow"
          priority
        />
      </div>
      <div>
        <p className="font-sans text-base text-foreground font-semibold">
          Resultado no disponible
        </p>
        <p className="font-mono text-[12px] text-subtext mt-1 max-w-[280px] leading-[1.6]">
          Los resultados de foto no se guardan entre sesiones. Escanea la etiqueta de nuevo.
        </p>
      </div>
      <Link
        href="/scan"
        className="px-6 py-3 rounded-button font-mono text-[12px] uppercase tracking-[0.08em] text-brand-green bs-glow-green"
        style={{ background: "rgba(74,222,128,.12)", border: "1px solid rgba(74,222,128,.3)" }}
      >
        ⟶ escanear de nuevo
      </Link>
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
