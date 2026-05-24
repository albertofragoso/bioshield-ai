"use client";

import { useEffect, useRef, useState } from "react";
import { getIngredientRisk, RISK_STYLES } from "@/lib/riskColors";
import { MascotGuide } from "@/components/marketing/MascotGuide";
import { FF_MASCOT_GUIDE } from "@/lib/featureFlags";

const STORY_STEPS = [
  {
    badge: "E407",
    name: "Carragenina",
    detail: "Espesante derivado de algas rojas",
    biomarker: "LDL",
    value: "165 mg/dL",
    status: "elevado",
    correlation:
      "Estudios en EFSA (2018) reportan correlaciones con marcadores inflamatorios en consumo frecuente.",
    ingredients: [
      { name: "Carragenina (E407)", biomarkerText: "Colesterol LDL ↑" },
      { name: "Almidón de maíz modificado", biomarkerText: null },
      { name: "Leche descremada", biomarkerText: null },
    ],
    conflicts: [
      { ingredient: "Carragenina", severity: "YELLOW" },
    ],
  },
  {
    badge: "E621",
    name: "Glutamato monosódico",
    detail: "Potenciador de sabor",
    biomarker: "Sodio",
    value: "148 mEq/L",
    status: "límite",
    correlation:
      "FDA EAFUS clasifica como GRAS con consumo moderado. En exceso puede afectar presión arterial.",
    ingredients: [
      { name: "Jarabe de maíz (JMAF)", biomarkerText: "Triglicéridos ↑" },
      { name: "Azúcar", biomarkerText: "Glucosa →" },
      { name: "Aceite de palma", biomarkerText: "HDL colesterol ↓" },
      { name: "Avena integral", biomarkerText: null },
      { name: "Miel", biomarkerText: null },
    ],
    conflicts: [
      { ingredient: "Jarabe de maíz", severity: "ORANGE" },
      { ingredient: "Azúcar", severity: "YELLOW" },
      { ingredient: "Aceite de palma", severity: "YELLOW" },
    ],
  },
  {
    badge: "E330",
    name: "Ácido cítrico",
    detail: "Conservante y acidulante",
    biomarker: "pH urinario",
    value: "5.2",
    status: "normal",
    correlation:
      "Sin correlaciones adversas reportadas en bases públicas regulatorias para consumo habitual.",
    ingredients: [
      { name: "Agua purificada", biomarkerText: null },
      { name: "Dióxido de carbono", biomarkerText: null },
    ],
    conflicts: [],
  },
];

export function RevealMomentStory() {
  const [active, setActive] = useState(0);
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), {
      threshold: 0.3,
    });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  const step = STORY_STEPS[active];

  return (
    <div
      ref={ref}
      className={`max-w-4xl mx-auto px-6 transition-all duration-700 ${
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
      }`}
    >
      {FF_MASCOT_GUIDE && (
        <div className="flex justify-center mb-8">
          <MascotGuide
            src="/avatars/progress.png"
            alt="BioShield mascota en modo descubrimiento"
            speech="Mira lo que encontré en tu producto…"
            size="md"
          />
        </div>
      )}

      <h2 className="font-sans text-3xl lg:text-4xl font-bold text-foreground text-center mb-4">
        Lo que tu etiqueta <span className="text-brand-amber">no te dice.</span>
      </h2>
      <p className="text-center text-subtext font-mono text-[12px] mb-12 max-w-lg mx-auto leading-relaxed">
        Cada aditivo tiene una historia. BioShield la cruza con tus análisis de laboratorio para que
        tengas contexto — no diagnóstico.
      </p>

      <div className="flex gap-3 justify-center mb-8">
        {STORY_STEPS.map((s, idx) => (
          <button
            key={s.badge}
            onClick={() => setActive(idx)}
            className="font-mono text-[11px] px-3 py-1.5 rounded-full border transition-colors"
            style={{
              borderColor: idx === active ? "var(--brand-amber)" : "var(--border)",
              color: idx === active ? "var(--brand-amber)" : "var(--subtext)",
              background: idx === active ? "rgba(245,158,11,.08)" : "transparent",
            }}
          >
            {s.badge}
          </button>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div
          className="border border-border rounded-card p-6"
          style={{ background: "var(--surface)" }}
        >
          <p className="font-mono text-[10px] text-subtext uppercase tracking-[0.1em] mb-2">
            Aditivo detectado
          </p>
          <h3 className="font-sans text-2xl font-bold text-foreground mb-1">{step?.name}</h3>
          <p className="font-mono text-[12px] text-subtext mb-4">{step?.detail}</p>
          <p className="font-mono text-[11px] text-subtext leading-relaxed mb-4">
            {step?.correlation}
          </p>

          {/* Ingredient → biomarker risk pills */}
          {step?.ingredients && step.ingredients.length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="font-mono text-[10px] text-subtext uppercase tracking-[0.1em] mb-1">
                Ingredientes
              </p>
              {step.ingredients.map(({ name, biomarkerText }) => {
                const level = getIngredientRisk(name, step.conflicts);
                const style = RISK_STYLES[level];
                return (
                  <div key={name} className="flex items-center gap-2 flex-wrap">
                    <span
                      className="text-xs px-2 py-1 rounded-full border"
                      style={{
                        color: style.text,
                        background: style.bg,
                        borderColor: style.border,
                      }}
                      aria-label={`${name} — ${style.ariaLabel}`}
                    >
                      {style.icon} {name}
                    </span>
                    {level !== "BLUE" && biomarkerText && (
                      <>
                        <span className="text-neutral-600 text-xs">→</span>
                        <span className="text-xs px-2 py-1 rounded-full bg-[#1a1a2e] text-violet-400 border border-[#2a2a4e]">
                          {biomarkerText}
                        </span>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div
          className="border border-border rounded-card p-6"
          style={{ background: "var(--surface)" }}
        >
          <p className="font-mono text-[10px] text-subtext uppercase tracking-[0.1em] mb-2">
            Tu laboratorio
          </p>
          <div className="flex items-center justify-between mb-4">
            <span className="font-sans text-2xl font-bold text-foreground">{step?.biomarker}</span>
            <span
              className="font-mono text-[11px] px-2 py-1 rounded"
              style={{
                background:
                  step?.status === "elevado"
                    ? "rgba(248,113,113,.1)"
                    : step?.status === "límite"
                      ? "rgba(245,158,11,.1)"
                      : "rgba(74,222,128,.1)",
                color:
                  step?.status === "elevado"
                    ? "#f87171"
                    : step?.status === "límite"
                      ? "#f59e0b"
                      : "#4ade80",
              }}
            >
              {step?.value}
            </span>
          </div>
          <p className="font-mono text-[10px] text-subtext italic">
            Para que decidas con tu médico — no es un diagnóstico.
          </p>
        </div>
      </div>
    </div>
  );
}
