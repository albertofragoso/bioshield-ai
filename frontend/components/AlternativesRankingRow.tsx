"use client";

import { AlternativeItem, SemaphoreColor } from "@/lib/api/types";
import { AvatarGlow } from "@/components/AvatarGlow";

const SEMAPHORE_CONFIG: Record<
  SemaphoreColor,
  { label: string; color: string; bg: string; border: string }
> = {
  BLUE:   { label: "Seguro",     color: "#4ade80", bg: "rgba(34,197,94,.1)",   border: "rgba(34,197,94,.18)"  },
  YELLOW: { label: "Precaución", color: "#fde047", bg: "rgba(250,204,21,.1)",  border: "rgba(250,204,21,.14)" },
  ORANGE: { label: "Riesgo",     color: "#fb923c", bg: "rgba(251,146,60,.1)",  border: "rgba(251,146,60,.14)" },
  RED:    { label: "Prohibido",  color: "#f87171", bg: "rgba(248,113,113,.1)", border: "rgba(248,113,113,.14)" },
  GRAY:   { label: "Sin datos",  color: "#9ca3af", bg: "rgba(156,163,175,.1)", border: "rgba(255,255,255,.06)" },
};

interface AlternativesRankingRowProps {
  item: AlternativeItem;
  position: number;
}

export function AlternativesRankingRow({ item, position }: AlternativesRankingRowProps) {
  const { product, avatar_variant, semaphore_precomputed } = item;
  const sem = SEMAPHORE_CONFIG[semaphore_precomputed] ?? SEMAPHORE_CONFIG.GRAY;
  const barWidth = `${product.clean_score}%`;
  const isNoData = semaphore_precomputed === "GRAY";

  return (
    <div
      className="flex items-center gap-4 rounded-[14px] border px-4 py-4 transition-all duration-150 hover:translate-x-[3px]"
      style={{
        background: "rgba(255,255,255,.03)",
        borderColor: sem.border,
        opacity: isNoData ? 0.6 : 1,
      }}
    >
      <span className="w-5 text-center text-[13px] font-bold text-[#334155]">
        {position}
      </span>
      <AvatarGlow
        variant={avatar_variant}
        size={56}
        intensity="soft"
      />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="truncate text-[13px] font-semibold text-[#e2e8f0]">
          {product.name ?? "Producto sin nombre"}
        </span>
        <span className="text-[11px] text-[#475569]">
          {product.brand ?? "Marca desconocida"}
        </span>
      </div>
      <div className="flex w-[80px] flex-shrink-0 flex-col items-end gap-1.5">
        <span
          className="inline-flex items-center rounded-[5px] px-1.5 py-0.5 text-[10px] font-semibold"
          style={{ background: sem.bg, color: sem.color }}
        >
          {sem.label}
        </span>
        {!isNoData && (
          <div className="flex w-full items-center gap-1.5">
            <div className="h-[4px] flex-1 rounded-full" style={{ background: "rgba(255,255,255,.07)" }}>
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: barWidth, background: sem.color }}
              />
            </div>
            <span className="text-[11px] font-bold" style={{ color: sem.color }}>
              {product.clean_score}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
