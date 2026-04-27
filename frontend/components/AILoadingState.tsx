"use client";

import { useState, useEffect, useRef } from "react";
import Image from "next/image";
import { Eye, FlaskConical, Activity, Shield, ChevronDown } from "lucide-react";

export interface AILoadingPhase {
  label: string;
  detail: string;
  /** Qué nodo orbital se ilumina (0–3) */
  nodeIndex: number;
  /** ms desde el mount hasta marcar como done. Infinity = nunca auto-completa. */
  completesAt: number;
}

export const SCAN_PHASES: AILoadingPhase[] = [
  {
    label: "READING_LABEL_OCR",
    detail: "Procesando con Gemini Vision 2.5 Flash · resolución adaptativa",
    nodeIndex: 0,
    completesAt: 1500,
  },
  {
    label: "TOKENIZING_INGREDIENTS",
    detail: "Extrayendo ingredientes, E-codes y valores nutricionales",
    nodeIndex: 0,
    completesAt: 4000,
  },
  {
    label: "SEMANTIC_SEARCH",
    detail: "Búsqueda vectorial · 2,847 aditivos indexados en ChromaDB",
    nodeIndex: 1,
    completesAt: 8000,
  },
  {
    label: "ADDITIVES_SCAN",
    detail: "Cruzando con base de datos de riesgos ocultos y conservantes",
    nodeIndex: 1,
    completesAt: 12000,
  },
  {
    label: "BIOMARKER_CROSS_REF",
    detail: "Comparando con tus biomarcadores · análisis de compatibilidad personal",
    nodeIndex: 2,
    completesAt: 17000,
  },
  {
    label: "SAFETY_SCORE_CALC",
    detail: "Calculando semáforo nutricional personalizado",
    nodeIndex: 3,
    completesAt: Infinity,
  },
];

export const BIOSYNC_PHASES: AILoadingPhase[] = [
  {
    label: "READING_PDF_OCR",
    detail: "Extrayendo texto del PDF con reconocimiento óptico",
    nodeIndex: 0,
    completesAt: 2000,
  },
  {
    label: "PARSING_LAB_RESULTS",
    detail: "Identificando valores de laboratorio y unidades de medida",
    nodeIndex: 0,
    completesAt: 5000,
  },
  {
    label: "NORMALIZING_BIOMARKERS",
    detail: "Normalizando nombres al estándar canónico BioShield",
    nodeIndex: 1,
    completesAt: 8000,
  },
  {
    label: "CLASSIFYING_VALUES",
    detail: "Clasificando valores según rangos de referencia clínicos",
    nodeIndex: 2,
    completesAt: 11000,
  },
  {
    label: "CROSS_REF_RANGES",
    detail: "Cruzando con rangos por edad y género · nada se guarda aún",
    nodeIndex: 3,
    completesAt: Infinity,
  },
];

const ORBITAL_NODES = [
  { Icon: Eye },
  { Icon: FlaskConical },
  { Icon: Activity },
  { Icon: Shield },
];

export function AILoadingState({ phases }: { phases: AILoadingPhase[] }) {
  const [completedPhases, setCompletedPhases] = useState<Set<number>>(new Set());
  const [activePhase, setActivePhase] = useState(0);
  const [expandedPhase, setExpandedPhase] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [avatarBounce, setAvatarBounce] = useState(false);
  const startRef = useRef(Date.now());

  useEffect(() => {
    const id = setInterval(() => {
      const ms = Date.now() - startRef.current;
      setElapsed(Math.floor(ms / 1000));

      setCompletedPhases((prev) => {
        let changed = false;
        const next = new Set(prev);
        phases.forEach((phase, i) => {
          if (phase.completesAt !== Infinity && ms >= phase.completesAt && !prev.has(i)) {
            next.add(i);
            changed = true;
          }
        });
        return changed ? next : prev;
      });

      setActivePhase(() => {
        for (let i = phases.length - 2; i >= 0; i--) {
          if (ms >= phases[i].completesAt) return i + 1;
        }
        return 0;
      });
    }, 200);

    return () => clearInterval(id);
  }, [phases]);

  const handleAvatarClick = () => {
    setAvatarBounce(true);
    setTimeout(() => setAvatarBounce(false), 500);
  };

  const litNodes = new Set(Array.from(completedPhases).map((i) => phases[i].nodeIndex));

  return (
    <div className="flex flex-col items-center gap-5 py-6">
      {/* ── Orbital avatar ── */}
      <div
        className="relative flex items-center justify-center"
        style={{ width: 240, height: 240 }}
      >
        {/* Outer — verde, 22s CW, dashed. Los nodos se apoyan visualmente aquí. */}
        <div
          className="absolute rounded-full pointer-events-none"
          style={{
            width: 226,
            height: 226,
            border: "1px dashed rgba(74,222,128,0.22)",
            boxShadow:
              "0 0 10px 2px rgba(74,222,128,0.12), inset 0 0 10px 2px rgba(74,222,128,0.06)",
            animation: "bs-orbit-cw 22s linear infinite",
          }}
        />
        {/* Mid-outer — teal, 14s CCW, solid */}
        <div
          className="absolute rounded-full pointer-events-none"
          style={{
            width: 182,
            height: 182,
            border: "1px solid rgba(45,212,191,0.18)",
            boxShadow:
              "0 0 9px 2px rgba(45,212,191,0.12), inset 0 0 9px 2px rgba(45,212,191,0.06)",
            animation: "bs-orbit-ccw 14s linear infinite",
          }}
        />
        {/* Mid — ámbar, 8s CW, dashed */}
        <div
          className="absolute rounded-full pointer-events-none"
          style={{
            width: 138,
            height: 138,
            border: "1px dashed rgba(245,158,11,0.18)",
            boxShadow:
              "0 0 7px 1px rgba(245,158,11,0.12), inset 0 0 7px 1px rgba(245,158,11,0.06)",
            animation: "bs-orbit-cw 8s linear infinite",
          }}
        />
        {/* Inner — verde suave, 5s CCW, solid */}
        <div
          className="absolute rounded-full pointer-events-none"
          style={{
            width: 96,
            height: 96,
            border: "1px solid rgba(74,222,128,0.1)",
            boxShadow: "0 0 5px 1px rgba(74,222,128,0.08)",
            animation: "bs-orbit-ccw 5s linear infinite",
          }}
        />

        {/* 4 nodos orbitales estáticos — se iluminan conforme avanzan las fases */}
        {ORBITAL_NODES.map((node, i) => {
          const angle = i * 90 - 90;
          const radius = 113;
          const rad = (angle * Math.PI) / 180;
          const x = Math.cos(rad) * radius;
          const y = Math.sin(rad) * radius;
          const isLit = litNodes.has(i);

          return (
            <div
              key={i}
              className="absolute flex items-center justify-center rounded-full transition-all duration-700"
              style={{
                width: 34,
                height: 34,
                left: `calc(50% + ${x}px - 17px)`,
                top: `calc(50% + ${y}px - 17px)`,
                background: isLit ? "rgba(74,222,128,0.14)" : "rgba(255,255,255,0.03)",
                border: `1px solid ${isLit ? "rgba(74,222,128,0.45)" : "rgba(255,255,255,0.07)"}`,
                boxShadow: isLit ? "0 0 10px rgba(74,222,128,0.28)" : "none",
                color: isLit ? "#4ade80" : "rgba(255,255,255,0.18)",
              }}
            >
              <node.Icon size={13} />
            </div>
          );
        })}

        {/* Avatar — tap para bounce */}
        <button
          onClick={handleAvatarClick}
          className={`relative z-10 bs-mascot-glow transition-transform duration-300 ${
            avatarBounce ? "scale-110" : "scale-100"
          }`}
          aria-label="BioShield procesando"
        >
          <Image
            src="/avatars/progress.png"
            alt=""
            aria-hidden
            width={110}
            height={110}
            className="object-contain"
            priority
          />
        </button>
      </div>

      {/* ── Terminal card ── */}
      <div
        className="w-full rounded-card overflow-hidden"
        style={{
          background: "rgba(0,0,0,0.45)",
          border: "1px solid rgba(74,222,128,0.12)",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-2"
          style={{
            borderBottom: "1px solid rgba(74,222,128,0.08)",
            background: "rgba(74,222,128,0.04)",
          }}
        >
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-green animate-pulse" aria-hidden />
            <span className="font-mono text-[10px] text-brand-green uppercase tracking-[0.12em]">
              BioShield AI · v2.5
            </span>
          </div>
          <span className="font-mono text-[10px] text-subtext">{elapsed}s</span>
        </div>

        {/* Log lines */}
        <div className="px-4 py-3 flex flex-col gap-1">
          {phases.map((phase, i) => {
            const isDone = completedPhases.has(i);
            const isActive = activePhase === i && !isDone;
            const isPending = i > activePhase;
            const isExpanded = expandedPhase === i;

            if (isPending) return null;

            return (
              <div key={i}>
                <button
                  onClick={() => isDone && setExpandedPhase(isExpanded ? null : i)}
                  disabled={!isDone}
                  className="w-full text-left flex items-center gap-2 py-0.5"
                >
                  <span
                    className="font-mono text-[11px] shrink-0 w-3"
                    style={{
                      color: isDone ? "#4ade80" : isActive ? "#f59e0b" : "rgba(255,255,255,0.25)",
                    }}
                  >
                    {isDone ? "✓" : isActive ? "›" : "·"}
                  </span>
                  <span
                    className="font-mono text-[11px] flex-1"
                    style={{
                      color: isDone
                        ? "rgba(74,222,128,0.85)"
                        : isActive
                          ? "#f59e0b"
                          : "rgba(255,255,255,0.3)",
                    }}
                  >
                    {phase.label}
                    {isActive && <span className="bs-cursor-blink ml-0.5">▊</span>}
                  </span>
                  {isDone && (
                    <ChevronDown
                      size={11}
                      className={`shrink-0 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                      style={{ color: "rgba(74,222,128,0.35)" }}
                    />
                  )}
                </button>

                {isExpanded && (
                  <div
                    className="mt-1 ml-5 px-2.5 py-1.5 rounded font-mono text-[10px]"
                    style={{
                      background: "rgba(74,222,128,0.05)",
                      border: "1px solid rgba(74,222,128,0.1)",
                      color: "rgba(74,222,128,0.65)",
                    }}
                  >
                    › {phase.detail}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
