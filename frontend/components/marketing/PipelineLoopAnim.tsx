"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { FF_RISK_PILLS } from "@/lib/featureFlags";
import { getIngredientRisk, RISK_STYLES } from "@/lib/riskColors";

interface SseEvent {
  t_ms: number;
  type: string;
  data: Record<string, unknown>;
}

interface ScanTrace {
  barcode: string;
  product_name: string;
  events: SseEvent[];
}

interface ConflictEntry {
  ingredient: string;
  severity: string;
}

const FIXTURE_BARCODES = ["7501055300072", "7501000510010", "7501055316981"];

const EVENT_LABELS: Record<string, string> = {
  init: "Iniciando análisis...",
  product_identified: "Producto identificado",
  ingredients: "Extrayendo ingredientes",
  entities_resolved: "Normalizando nombres",
  regulatory_search: "Consultando FDA · EFSA · Codex",
  biosync: "Cruzando con tu laboratorio",
  conflicts: "Detectando correlaciones",
  personalized: "Personalizando resultados",
  risk: "Calculando perfil",
  done: "Análisis completo",
};

const SEMAPHORE_BAR_WIDTH: Record<string, string> = {
  ORANGE: "75%",
  YELLOW: "45%",
  BLUE: "15%",
};

interface PipelineLoopAnimProps {
  onOpenDemo?: () => void;
}

export function PipelineLoopAnim({ onOpenDemo }: PipelineLoopAnimProps) {
  const [traces, setTraces] = useState<ScanTrace[]>([]);
  const [currentTraceIdx, setCurrentTraceIdx] = useState(0);
  const [currentEventIdx, setCurrentEventIdx] = useState(0);
  const [isPlaying] = useState(true);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Extra state for split layout
  const [ingredients, setIngredients] = useState<string[]>([]);
  const [conflicts, setConflicts] = useState<ConflictEntry[]>([]);
  const [semaphore, setSemaphore] = useState<string | null>(null);

  useEffect(() => {
    Promise.all(
      FIXTURE_BARCODES.map(async (barcode) => {
        const resp = await fetch(`/demo/scan-trace-${barcode}.json`);
        if (!resp.ok) throw new Error(`Demo fixture ${barcode} returned ${resp.status}`);
        return resp.json() as Promise<ScanTrace>;
      })
    )
      .then(setTraces)
      .catch((err) => console.error("[PipelineLoopAnim] fetch failed:", err));
  }, []);

  const advanceEvent = useCallback(() => {
    if (!traces.length || !isPlaying) return;

    const trace = traces[currentTraceIdx];
    if (!trace) return;

    const nextIdx = currentEventIdx + 1;

    if (nextIdx >= trace.events.length) {
      timeoutRef.current = setTimeout(() => {
        setCurrentEventIdx(0);
        setCurrentTraceIdx((idx) => (idx + 1) % traces.length);
        // Reset split-layout state on loop
        setIngredients([]);
        setConflicts([]);
        setSemaphore(null);
      }, 2000);
      return;
    }

    const currentEvent = trace.events[currentEventIdx];
    const nextEvent = trace.events[nextIdx];
    const delay = nextEvent.t_ms - currentEvent.t_ms;

    timeoutRef.current = setTimeout(
      () => {
        setCurrentEventIdx(nextIdx);

        // Populate split-layout state as events arrive
        if (nextEvent.type === "ingredients") {
          const raw = nextEvent.data.ingredients;
          if (Array.isArray(raw)) {
            setIngredients(raw.map((item) => String(item)));
          }
        } else if (nextEvent.type === "conflicts") {
          const raw = nextEvent.data.conflicts;
          if (Array.isArray(raw)) {
            setConflicts(
              raw.map((c: Record<string, unknown>) => ({
                ingredient: String(c.ingredient ?? ""),
                severity: String(c.severity ?? ""),
              }))
            );
          }
        } else if (nextEvent.type === "risk") {
          const sem = nextEvent.data.semaphore;
          if (typeof sem === "string") setSemaphore(sem);
        }
      },
      Math.max(delay, 100)
    );
  }, [traces, currentTraceIdx, currentEventIdx, isPlaying]);

  useEffect(() => {
    advanceEvent();
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [advanceEvent]);

  if (!traces.length) {
    return (
      <div className="w-full max-w-sm h-64 flex items-center justify-center">
        <p className="font-mono text-[11px] text-subtext animate-pulse">Cargando demo...</p>
      </div>
    );
  }

  const trace = traces[currentTraceIdx];
  const visibleEvents = trace?.events.slice(0, currentEventIdx + 1) ?? [];
  const isDone = visibleEvents.at(-1)?.type === "done";

  // ── Split layout (FF_RISK_PILLS = true) ─────────────────────────────────────
  if (FF_RISK_PILLS) {
    const barWidth = semaphore ? (SEMAPHORE_BAR_WIDTH[semaphore.toUpperCase()] ?? "15%") : "0%";

    return (
      <div className="relative w-full max-w-2xl">
        <div
          className="border border-border rounded-card font-mono text-[11px] overflow-hidden"
          style={{ background: "var(--surface)" }}
        >
          {/* Titlebar */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-border">
            <div className="flex items-center gap-2">
              {/* macOS dots */}
              <span className="w-3 h-3 rounded-full bg-red-500 shrink-0" />
              <span className="w-3 h-3 rounded-full bg-yellow-400 shrink-0" />
              <span className="w-3 h-3 rounded-full bg-green-500 shrink-0" />
              <span className="ml-2 text-subtext text-[10px]">BioShield · Pipeline en vivo</span>
            </div>
            <div className="flex items-center gap-2 text-subtext text-[10px] shrink-0">
              <span className="truncate max-w-[120px]">{trace?.product_name ?? "..."}</span>
              <span className="opacity-50">{trace?.barcode}</span>
            </div>
          </div>

          {/* Two-column body */}
          <div className="flex divide-x divide-border">
            {/* Left: Pipeline events */}
            <div className="flex-1 p-3 space-y-1.5 min-h-[160px]">
              {visibleEvents.map((event, idx) => {
                const isActive = idx === visibleEvents.length - 1 && !isDone;
                const isDoneEvent = event.type === "done";
                return (
                  <div key={idx} className="flex items-center gap-2">
                    {/* Dot */}
                    <span
                      className={[
                        "w-2 h-2 rounded-full shrink-0",
                        isDoneEvent
                          ? "bg-green-500"
                          : isActive
                            ? "bg-teal-400 motion-safe:animate-pulse"
                            : "bg-neutral-600",
                      ].join(" ")}
                    />
                    {/* Label */}
                    <span
                      className={
                        isDoneEvent
                          ? "text-green-400"
                          : isActive
                            ? "text-white"
                            : "text-subtext opacity-60"
                      }
                    >
                      {EVENT_LABELS[event.type] ?? event.type}
                    </span>
                    {/* Timing */}
                    <span className="ml-auto text-[10px] text-subtext opacity-50 shrink-0">
                      {event.t_ms}ms
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Right: Ingredients + risk */}
            <div
              className="flex-1 p-3 min-h-[160px] flex flex-col gap-2"
              aria-label="Ingredientes detectados"
            >
              {ingredients.length === 0 ? (
                <p className="text-subtext opacity-40 text-[10px] mt-auto mb-auto">
                  Esperando ingredientes...
                </p>
              ) : (
                <>
                  {/* Ingredient pills */}
                  <div className="flex flex-col gap-1 overflow-y-auto max-h-[120px]">
                    {ingredients.map((name) => {
                      const level = getIngredientRisk(name, conflicts);
                      const style = RISK_STYLES[level];
                      return (
                        <span
                          key={name}
                          aria-label={`${name} — ${style.ariaLabel}`}
                          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] border shrink-0"
                          style={{
                            color: style.text,
                            background: style.bg,
                            borderColor: style.border,
                          }}
                        >
                          <span aria-hidden="true">{style.icon}</span>
                          <span className="truncate max-w-[140px]">{name}</span>
                        </span>
                      );
                    })}
                  </div>

                  {/* Risk progress bar */}
                  {semaphore && (
                    <div className="mt-auto">
                      <p className="text-subtext text-[10px] mb-1">
                        Riesgo:{" "}
                        <span className="text-white font-semibold">{semaphore}</span>
                      </p>
                      <div className="h-1.5 bg-border rounded overflow-hidden">
                        <div
                          className="h-full rounded bg-gradient-to-r from-teal-500 via-yellow-400 to-red-400 transition-all duration-500"
                          style={{ width: barWidth }}
                        />
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Disclaimer footer */}
          <div className="border-t border-border px-3 py-1.5">
            <p className="text-center text-[10px] text-subtext">
              ⚠ Simulación con datos reales pre-grabados · No consejo médico
            </p>
          </div>
        </div>

        {onOpenDemo && isDone && (
          <button
            onClick={onOpenDemo}
            className="mt-3 w-full font-mono text-[11px] text-brand-green rounded-button py-2 transition-colors"
            style={{ border: "1px solid rgba(74,222,128,.3)" }}
          >
            Ver demo completo →
          </button>
        )}
      </div>
    );
  }

  // ── Fallback: old single-column layout ──────────────────────────────────────
  return (
    <div className="relative w-full max-w-sm">
      <div
        className="border border-border rounded-card p-4 font-mono text-[11px]"
        style={{ background: "var(--surface)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-3 pb-2 border-b border-border">
          <span className="text-brand-green truncate">{trace?.product_name ?? "..."}</span>
          <span className="text-subtext text-[10px] shrink-0 ml-2">
            {currentTraceIdx + 1}/{traces.length}
          </span>
        </div>

        {/* Eventos */}
        <div className="space-y-1.5 min-h-[120px]">
          {visibleEvents.map((event, idx) => (
            <div key={idx} className="flex items-center gap-2 text-subtext">
              <span
                className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                  idx === visibleEvents.length - 1 && !isDone
                    ? "bg-brand-green animate-pulse"
                    : "bg-subtext"
                }`}
              />
              <span className={event.type === "done" ? "text-brand-green" : undefined}>
                {EVENT_LABELS[event.type] ?? event.type}
              </span>
              <span className="ml-auto text-[10px] shrink-0">{event.t_ms}ms</span>
            </div>
          ))}
        </div>

        {/* Progress bar */}
        <div className="mt-3 h-[2px] bg-border rounded overflow-hidden">
          <div
            className="h-full bg-brand-green transition-all duration-300"
            style={{
              width: `${((currentEventIdx + 1) / (trace?.events.length ?? 1)) * 100}%`,
            }}
          />
        </div>
      </div>

      {/* Compliance watermark */}
      <p className="mt-2 text-center font-mono text-[10px] text-subtext">
        Simulación con datos reales pre-grabados
      </p>

      {onOpenDemo && isDone && (
        <button
          onClick={onOpenDemo}
          className="mt-3 w-full font-mono text-[11px] text-brand-green rounded-button py-2 transition-colors"
          style={{ border: "1px solid rgba(74,222,128,.3)" }}
        >
          Ver demo completo →
        </button>
      )}
    </div>
  );
}
