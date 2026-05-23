"use client";

import { useEffect, useRef, useState } from "react";

const STEPS = [
  { id: 1, icon: "📷", title: "Escaneás", desc: "Foto o código de barras", highlight: false },
  { id: 2, icon: "🔍", title: "Reconocemos", desc: "Ingredientes y aditivos", highlight: false },
  {
    id: 3,
    icon: "📋",
    title: "Cruzamos",
    desc: "FDA · EFSA · Codex Alimentarius",
    highlight: false,
  },
  {
    id: 4,
    icon: "🩸",
    title: "Comparamos",
    desc: "Con tus análisis de laboratorio",
    highlight: false,
  },
  {
    id: 5,
    icon: "📊",
    title: "Te mostramos",
    desc: "Correlaciones informativas — no diagnóstico",
    highlight: true,
  },
];

export function HowItHelpsGraph() {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), {
      threshold: 0.2,
    });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className="max-w-4xl mx-auto px-6">
      <h2 className="font-sans text-3xl lg:text-4xl font-bold text-center text-foreground mb-16">
        Cómo te ayuda BioShield
      </h2>

      <div className="flex flex-col lg:flex-row items-stretch gap-3">
        {STEPS.map((step, idx) => (
          <div
            key={step.id}
            className={`flex-1 border rounded-card p-4 transition-all duration-500 ${
              visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
            }`}
            style={{
              transitionDelay: `${idx * 80}ms`,
              background: "var(--surface)",
              borderColor: step.highlight ? "var(--brand-green)" : "var(--border)",
              boxShadow: step.highlight ? "0 0 20px rgba(74,222,128,.12)" : "none",
            }}
          >
            <div className="text-2xl mb-3">{step.icon}</div>
            <h3
              className="font-sans font-semibold text-sm mb-1"
              style={{ color: step.highlight ? "var(--brand-green)" : "var(--foreground)" }}
            >
              {step.title}
            </h3>
            <p className="font-mono text-[10px] text-subtext">{step.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
