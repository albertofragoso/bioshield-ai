"use client";

import { useEffect, useRef, useState } from "react";
import { MascotGuide } from "@/components/marketing/MascotGuide";
import { FF_MASCOT_GUIDE } from "@/lib/featureFlags";
import { Drop } from "@phosphor-icons/react/dist/csr/Drop";
import { MagnifyingGlass } from "@phosphor-icons/react/dist/csr/MagnifyingGlass";
import { Lightning } from "@phosphor-icons/react/dist/csr/Lightning";
import { Globe } from "@phosphor-icons/react/dist/csr/Globe";
import type { Icon } from "@phosphor-icons/react";

type Feature = {
  Icon: Icon;
  iconColor: string;
  name: string;
  bioDesc: string;
  otherDesc: string;
  hasBio: boolean;
  hasOther: boolean | "partial";
};

const FEATURES: Feature[] = [
  {
    Icon: Drop,
    iconColor: "#F87171",
    name: "Cruce con biomarkers",
    bioDesc: "Personalizado a tus resultados de sangre",
    otherDesc: "No disponible",
    hasBio: true,
    hasOther: false,
  },
  {
    Icon: MagnifyingGlass,
    iconColor: "#4ADE80",
    name: "Búsqueda semántica",
    bioDesc: "Detecta aditivos por nombre comercial y genérico",
    otherDesc: "Solo keywords exactas",
    hasBio: true,
    hasOther: false,
  },
  {
    Icon: Lightning,
    iconColor: "#F59E0B",
    name: "Análisis en tiempo real",
    bioDesc: "Pipeline SSE — resultados en <3s",
    otherDesc: "Respuesta batch, sin streaming",
    hasBio: true,
    hasOther: false,
  },
  {
    Icon: Globe,
    iconColor: "#4ADE80",
    name: "Base de datos global",
    bioDesc: "Open Food Facts + USDA (millones de productos)",
    otherDesc: "Solo productos locales",
    hasBio: true,
    hasOther: "partial" as const,
  },
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
      {FF_MASCOT_GUIDE && (
        <div className="flex justify-center mb-8">
          <MascotGuide
            src="/avatars/success.png"
            alt="BioShield mascota orgullosa de sus capacidades"
            speech="Ninguna otra app hace esto junto."
            size="md"
          />
        </div>
      )}

      <h2 className="font-sans text-3xl lg:text-4xl font-bold text-center text-foreground mb-4">
        Otras apps te dicen calorías.
        <br />
        <span className="text-brand-green">BioShield contextualiza con TU sangre.</span>
      </h2>
      <p className="text-center font-mono text-[12px] text-subtext mb-12">
        La diferencia está en los datos que cruza.
      </p>

      {/* 2-column feature cards — 1 col on mobile, 2 on sm+ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* BioShield column */}
        <div className="border border-teal-700 rounded-xl overflow-hidden">
          <div className="bg-teal-900/30 px-4 py-3 border-b border-teal-700 flex items-center gap-2">
            <span aria-hidden="true">🛡️</span>
            <span className="text-teal-400 font-semibold">BioShield AI</span>
          </div>
          {FEATURES.map((f) => (
            <div
              key={f.name}
              className="flex items-center gap-3 px-4 py-3 border-b border-[#0a0a12] last:border-b-0"
            >
              <div className="w-8 h-8 rounded-lg bg-teal-900/40 flex items-center justify-center flex-shrink-0">
                <f.Icon weight="duotone" size={18} color={f.iconColor} />
              </div>
              <div className="min-w-0">
                <p className="text-sm text-neutral-200">{f.name}</p>
                <p className="text-xs text-neutral-500">{f.bioDesc}</p>
              </div>
              <span className="text-emerald-400 text-lg ml-auto">✅</span>
            </div>
          ))}
        </div>

        {/* Other apps column */}
        <div className="border border-[#1a1a2e] rounded-xl overflow-hidden">
          <div className="bg-[#0a0a0f] px-4 py-3 border-b border-[#1a1a2e] flex items-center gap-2">
            <span aria-hidden="true">📱</span>
            <span className="text-neutral-500 font-semibold">Otras apps</span>
          </div>
          {FEATURES.map((f) => (
            <div
              key={f.name}
              className="flex items-center gap-3 px-4 py-3 border-b border-[#0a0a12] last:border-b-0"
            >
              <div className="w-8 h-8 rounded-lg bg-[#111] flex items-center justify-center flex-shrink-0">
                <f.Icon weight="duotone" size={18} color="#4B5563" />
              </div>
              <div className="min-w-0">
                <p className="text-sm text-neutral-600">{f.name}</p>
                <p className="text-xs text-neutral-700">{f.otherDesc}</p>
              </div>
              <span className="text-neutral-700 text-lg ml-auto">
                {f.hasOther === "partial" ? "~" : "✗"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
