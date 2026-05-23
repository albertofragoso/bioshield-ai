"use client";

import { useEffect, useRef, useState, useCallback } from "react";

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

interface PipelineLoopAnimProps {
  onOpenDemo?: () => void;
}

export function PipelineLoopAnim({ onOpenDemo }: PipelineLoopAnimProps) {
  const [traces, setTraces] = useState<ScanTrace[]>([]);
  const [currentTraceIdx, setCurrentTraceIdx] = useState(0);
  const [currentEventIdx, setCurrentEventIdx] = useState(0);
  const [isPlaying] = useState(true);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    Promise.all(
      FIXTURE_BARCODES.map(async (barcode) => {
        const resp = await fetch(`/demo/scan-trace-${barcode}.json`);
        return resp.json() as Promise<ScanTrace>;
      })
    ).then(setTraces);
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
      }, 2000);
      return;
    }

    const currentEvent = trace.events[currentEventIdx];
    const nextEvent = trace.events[nextIdx];
    const delay = nextEvent.t_ms - currentEvent.t_ms;

    timeoutRef.current = setTimeout(
      () => {
        setCurrentEventIdx(nextIdx);
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
