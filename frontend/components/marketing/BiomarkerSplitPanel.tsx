"use client";

import { useEffect, useRef, useState } from "react";

const COMPARISON_ROWS = [
  { feature: "Lectura de etiqueta", others: "✓", bioshield: "✓" },
  { feature: "Semáforo nutricional", others: "✓", bioshield: "✓" },
  { feature: "Aditivos E-number", others: "Parcial", bioshield: "✓ completo" },
  { feature: "Fuentes regulatorias citadas", others: "✗", bioshield: "FDA · EFSA · Codex" },
  { feature: "Cruce con tus análisis de lab", others: "✗", bioshield: "✓" },
  { feature: "Alternativas personalizadas", others: "✗", bioshield: "✓" },
  { feature: "Datos cifrados AES-256", others: "✗", bioshield: "✓" },
];

export function BiomarkerSplitPanel() {
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
    <div
      ref={ref}
      className={`max-w-4xl mx-auto px-6 transition-all duration-700 ${
        visible ? "opacity-100" : "opacity-0"
      }`}
    >
      <h2 className="font-sans text-3xl lg:text-4xl font-bold text-center text-foreground mb-4">
        Otras apps te dicen calorías.
        <br />
        <span className="text-brand-green">BioShield contextualiza con TU sangre.</span>
      </h2>
      <p className="text-center font-mono text-[12px] text-subtext mb-12">
        La diferencia está en los datos que cruza.
      </p>

      <div className="overflow-x-auto">
        <table className="w-full font-mono text-[12px]">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <th className="text-left py-3 px-4 text-subtext font-normal">Capacidad</th>
              <th className="text-center py-3 px-4 text-subtext font-normal">Otras apps</th>
              <th className="text-center py-3 px-4 text-brand-green font-semibold">BioShield</th>
            </tr>
          </thead>
          <tbody>
            {COMPARISON_ROWS.map((row) => (
              <tr key={row.feature} style={{ borderBottom: "1px solid rgba(74,222,128,.06)" }}>
                <td className="py-3 px-4 text-subtext">{row.feature}</td>
                <td className="py-3 px-4 text-center text-subtext">{row.others}</td>
                <td className="py-3 px-4 text-center text-brand-green font-medium">
                  {row.bioshield}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
