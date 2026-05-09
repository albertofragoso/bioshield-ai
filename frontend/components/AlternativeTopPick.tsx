"use client";

import Link from "next/link";
import { AvatarGlow } from "@/components/AvatarGlow";
import type { AlternativeTopPick as TopPickData, AvatarVariant } from "@/lib/api/types";

interface AlternativeTopPickProps {
  data: TopPickData;
  hasBiomarkers: boolean;
}

export function AlternativeTopPick({ data, hasBiomarkers }: AlternativeTopPickProps) {
  const { product, clean_ingredients, biomarker_conflicts, compatibility_pct, avatar_variant } = data;

  return (
    <div className="rounded-[14px] overflow-hidden border border-[rgba(96,165,250,.35)]">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-[rgba(30,58,138,.25)] border-b border-[rgba(96,165,250,.15)]">
        <span className="font-mono text-[10px] font-bold text-[#93c5fd] uppercase tracking-[0.08em]">
          ⭐ Mejor match para ti
        </span>
        <span className="font-mono text-[11px] text-[#60a5fa]">{compatibility_pct}% compatible</span>
      </div>

      {/* Body */}
      <div className="flex items-start gap-3 p-4 bg-[rgba(12,24,40,.6)] relative">
        {/* Ambient glow */}
        <div
          className="absolute top-0 left-1/2 -translate-x-1/2 pointer-events-none"
          style={{
            width: 200,
            height: 100,
            background: "radial-gradient(ellipse at top, rgba(96,165,250,.10) 0%, transparent 70%)",
            borderRadius: "0 0 100% 100%",
          }}
        />

        <div className="flex flex-col items-center gap-1 shrink-0 relative z-10">
          <AvatarGlow variant={avatar_variant as AvatarVariant} size={88} intensity="strong" />
          <span className="font-mono text-[9px] text-[#60a5fa] font-semibold uppercase tracking-[0.06em]">
            Seguro
          </span>
        </div>

        <div className="flex-1 min-w-0 relative z-10">
          <p className="font-sans font-bold text-[17px] text-[#bfdbfe] leading-tight">{product.name}</p>
          <p className="text-[11px] text-[#475569] mt-0.5 mb-3">{product.brand}</p>
          {clean_ingredients.map((label) => (
            <p key={label} className="text-[11px] text-[#60a5fa] mb-1">
              ✓ {label}
            </p>
          ))}
        </div>
      </div>

      {/* Biomarker insight / CTA to BioSync */}
      <div className="px-3 py-2 border-t border-[rgba(96,165,250,.15)] bg-[rgba(30,58,138,.15)]">
        {hasBiomarkers ? (
          <p className="text-[11px] text-[#93c5fd]">
            💊{" "}
            {biomarker_conflicts.length === 0
              ? "Sin conflictos con tus biomarcadores"
              : biomarker_conflicts.slice(0, 2).join(" · ")}
          </p>
        ) : (
          <Link
            href="/biosync"
            className="flex items-center gap-1.5 text-[11px] text-[#93c5fd] hover:text-[#60a5fa] transition-colors"
          >
            🔒 Personaliza con tus biomarcadores →
          </Link>
        )}
      </div>

      {/* CTA */}
      <div className="px-3 py-2.5 bg-[rgba(15,30,60,.5)] border-t border-[rgba(96,165,250,.10)]">
        <Link
          href={`/scan/${product.barcode}`}
          className="block bg-[#2563eb] text-white text-center py-2 px-4 rounded-lg text-[13px] font-semibold hover:bg-[#1d4ed8] transition-colors"
        >
          Ver análisis completo →
        </Link>
      </div>
    </div>
  );
}
