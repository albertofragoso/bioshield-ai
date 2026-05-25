"use client";

import { IconLabel } from "./icons/IconLabel";
import { IconENumber } from "./icons/IconENumber";
import { IconBloodDrop } from "./icons/IconBloodDrop";
import { IconShieldDNA } from "./icons/IconShieldDNA";

export const BEATS = [
  {
    icon: "label",
    headline: "Lo que crees saber",
    body: "5g proteína · Bajo en grasa · Sin azúcar añadida. Llevas meses comprando este yogurt. Confías en él.",
    accentColor: "#4ADE80",
  },
  {
    icon: "enumber",
    headline: "Lo que hay realmente",
    body: "Al fondo de la etiqueta, 3 aditivos con nombres que no puedes pronunciar. Aprobados. Legales. Pero ahí están.",
    pills: ["E407 Carragenina", "E621 Glutamato", "E202 Sorbato"],
    accentColor: "#F59E0B",
  },
  {
    icon: "blood",
    headline: "Lo que significa para ti",
    body: "Si tu perfil muestra marcadores de inflamación elevados, BioShield cruza ese dato aquí — así se vería tu análisis.",
    disclaimer: "Ejemplo ilustrativo · Datos reales solo con tu perfil activo",
    accentColor: "#F87171",
  },
  {
    icon: "shield",
    headline: "La brecha cerrada",
    body: "Entre lo que dice la etiqueta y lo que significa para tu cuerpo. BioShield la cierra en 3 segundos.",
    accentColor: "#4ADE80",
    cta: true,
  },
] as const;

type Beat = (typeof BEATS)[number];

function BeatIcon({ icon }: { icon: Beat["icon"] }) {
  switch (icon) {
    case "label":
      return <IconLabel size={32} className="shrink-0" />;
    case "enumber":
      return <IconENumber size={32} className="shrink-0" />;
    case "blood":
      return <IconBloodDrop size={32} className="shrink-0" />;
    case "shield":
      return <IconShieldDNA size={32} className="shrink-0" />;
  }
}

export function StaticBeats() {
  return (
    <section className="w-full py-16 px-4 sm:px-8" style={{ backgroundColor: "#080C07" }}>
      <div className="max-w-2xl mx-auto flex flex-col gap-8">
        {BEATS.map((beat, i) => {
          const hasPills = "pills" in beat && beat.pills;
          const hasDisclaimer = "disclaimer" in beat && beat.disclaimer;
          const hasCta = "cta" in beat && beat.cta;

          return (
            <div
              key={i}
              className="rounded-2xl border p-6 flex flex-col gap-4"
              style={{
                borderColor: `${beat.accentColor}33`,
                backgroundColor: "#0D1410",
              }}
            >
              {/* Icon + Headline */}
              <div className="flex items-center gap-3">
                <BeatIcon icon={beat.icon} />
                <h3
                  className="font-semibold text-lg leading-snug"
                  style={{ color: beat.accentColor, fontFamily: "Space Grotesk, sans-serif" }}
                >
                  {beat.headline}
                </h3>
              </div>

              {/* Body */}
              <p
                className="text-sm leading-relaxed"
                style={{ color: "#A8C5A8", fontFamily: "Space Grotesk, sans-serif" }}
              >
                {beat.body}
              </p>

              {/* Pills */}
              {hasPills && (
                <div className="flex flex-wrap gap-2">
                  {(beat as { pills: readonly string[] }).pills.map((pill) => (
                    <span
                      key={pill}
                      className="px-3 py-1 rounded-full text-xs font-medium"
                      style={{
                        backgroundColor: "#F59E0B22",
                        color: "#F59E0B",
                        fontFamily: "JetBrains Mono, monospace",
                        border: "1px solid #F59E0B44",
                      }}
                    >
                      {pill}
                    </span>
                  ))}
                </div>
              )}

              {/* Disclaimer */}
              {hasDisclaimer && (
                <p
                  className="text-xs"
                  style={{ color: "#6B8A6A", fontFamily: "Space Grotesk, sans-serif" }}
                >
                  {(beat as { disclaimer: string }).disclaimer}
                </p>
              )}

              {/* CTA */}
              {hasCta && (
                <a
                  href="#waitlist"
                  className="inline-block mt-2 px-6 py-3 rounded-xl text-sm font-semibold text-center transition-opacity hover:opacity-90"
                  style={{
                    backgroundColor: "#4ADE80",
                    color: "#080C07",
                    fontFamily: "Space Grotesk, sans-serif",
                  }}
                >
                  Únete a la lista de espera →
                </a>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
