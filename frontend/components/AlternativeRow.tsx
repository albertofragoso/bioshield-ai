"use client";

import Link from "next/link";
import { AvatarGlow } from "@/components/AvatarGlow";
import type { AlternativeItem, AvatarVariant } from "@/lib/api/types";

const SEMAPHORE_LABEL: Record<string, string> = {
  BLUE: "Seguro",
  YELLOW: "Precaución",
  ORANGE: "Riesgo",
  RED: "Prohibido",
  GRAY: "Sin datos",
};

const SEMAPHORE_COLORS: Record<string, { bg: string; text: string }> = {
  BLUE:   { bg: "rgba(37,99,235,.25)",  text: "#60a5fa" },
  YELLOW: { bg: "rgba(161,130,0,.25)",  text: "#facc15" },
  ORANGE: { bg: "rgba(154,52,18,.25)",  text: "#fb923c" },
  RED:    { bg: "rgba(127,29,29,.25)",  text: "#f87171" },
  GRAY:   { bg: "rgba(75,85,99,.25)",   text: "#9ca3af" },
};

interface AlternativeRowProps {
  item: AlternativeItem;
}

export function AlternativeRow({ item }: AlternativeRowProps) {
  const { product, avatar_variant, semaphore_precomputed } = item;
  const colors = SEMAPHORE_COLORS[semaphore_precomputed] ?? SEMAPHORE_COLORS.GRAY;
  const label = SEMAPHORE_LABEL[semaphore_precomputed] ?? "General";

  return (
    <Link
      href={`/scan/${product.barcode}`}
      className="flex items-center gap-3 px-3 py-2.5 rounded-[10px] border border-[#1a2318] bg-[#0b150b] hover:border-[#2d3f2d] transition-colors"
    >
      {/* Avatar — soft, slow pulse */}
      <AvatarGlow
        variant={avatar_variant as AvatarVariant}
        size={40}
        intensity="soft"
        className="[animation-duration:4s]"
      />

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-[13px] font-semibold text-[#cbd5e1] truncate">{product.name}</p>
        <p className="text-[11px] text-[#475569]">{product.brand}</p>
      </div>

      {/* Semaphore badge */}
      <div className="flex flex-col items-center gap-0.5 shrink-0">
        <span
          className="px-2 py-0.5 rounded-full text-[11px] font-bold"
          style={{ background: colors.bg, color: colors.text }}
        >
          {label}
        </span>
        <span className="text-[9px] text-[#334155]">general</span>
      </div>
    </Link>
  );
}
