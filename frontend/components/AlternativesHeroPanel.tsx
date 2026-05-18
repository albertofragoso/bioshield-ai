import { AlternativesResponse } from "@/lib/api/types";
import { AvatarGlow } from "@/components/AvatarGlow";
import type { AvatarVariant } from "@/lib/api/types";

const SEMAPHORE_COLORS: Record<string, string> = {
  BLUE:   "#22c55e",
  YELLOW: "#facc15",
  ORANGE: "#fb923c",
  RED:    "#f87171",
  GRAY:   "#9ca3af",
};

const SEMAPHORE_BLOCK: Record<string, { bg: string; border: string }> = {
  BLUE:   { bg: "rgba(34,197,94,.05)",    border: "1px solid rgba(34,197,94,.22)" },
  YELLOW: { bg: "rgba(250,204,21,.05)",   border: "1px solid rgba(250,204,21,.2)" },
  ORANGE: { bg: "rgba(251,146,60,.05)",   border: "1px solid rgba(251,146,60,.18)" },
  RED:    { bg: "rgba(248,113,113,.05)",  border: "1px solid rgba(248,113,113,.18)" },
  GRAY:   { bg: "rgba(156,163,175,.05)",  border: "1px solid rgba(156,163,175,.15)" },
};

interface AlternativesHeroPanelProps {
  data: AlternativesResponse;
}

export function AlternativesHeroPanel({ data }: AlternativesHeroPanelProps) {
  const { scanned_product, top_pick, has_biomarkers } = data;

  if (!top_pick) return null;

  const delta = top_pick.product.clean_score - scanned_product.clean_score;
  const scannedSemColor = SEMAPHORE_COLORS[scanned_product.semaphore] ?? "#9ca3af";
  // convierte BLUE/YELLOW/ORANGE/RED/GRAY → blue/yellow/orange/red/gray
  const scannedAvatarVariant = scanned_product.semaphore.toLowerCase() as AvatarVariant;

  return (
    <aside className="sticky flex flex-col gap-4" style={{ top: "72px" }}>
      <span className="text-[10px] font-semibold uppercase tracking-[.1em] text-[#334155]">
        Comparación directa
      </span>
      <div
        className="flex flex-col gap-4 rounded-[18px] border p-5"
        style={{
          background: "linear-gradient(145deg, rgba(12,24,40,.7) 0%, rgba(8,14,8,.5) 100%)",
          borderColor: "rgba(96,165,250,.25)",
        }}
      >
        {/* fila vs */}
        <div className="grid gap-2" style={{ gridTemplateColumns: "1fr 32px 1fr" }}>
          <div
            className="flex flex-col items-center gap-2 rounded-[14px] p-3 text-center"
            style={{
              background: SEMAPHORE_BLOCK[scanned_product.semaphore]?.bg ?? SEMAPHORE_BLOCK.GRAY.bg,
              border: SEMAPHORE_BLOCK[scanned_product.semaphore]?.border ?? SEMAPHORE_BLOCK.GRAY.border,
            }}
          >
            <AvatarGlow
              variant={scannedAvatarVariant}
              size={52}
              intensity="soft"
            />
            <span className="text-[11px] font-semibold leading-tight text-[#cbd5e1]">
              {scanned_product.name ?? "Producto escaneado"}
            </span>
            {scanned_product.brand && (
              <span className="text-[10px] text-[#475569]">{scanned_product.brand}</span>
            )}
            <span className="text-[20px] font-extrabold leading-none" style={{ color: scannedSemColor }}>
              {scanned_product.clean_score}
            </span>
            {top_pick.biomarker_conflicts.length > 0 && (
              <span className="text-[10px]" style={{ color: scannedSemColor }}>
                {top_pick.biomarker_conflicts.length} conflicto{top_pick.biomarker_conflicts.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
          <div className="flex items-center justify-center text-[12px] font-bold text-[#334155]">
            vs
          </div>
          <div
            className="flex flex-col items-center gap-2 rounded-[14px] p-3 text-center"
            style={{ background: "rgba(34,197,94,.05)", border: "1px solid rgba(34,197,94,.22)" }}
          >
            <AvatarGlow
              variant={top_pick.avatar_variant}
              size={52}
              intensity="strong"
            />
            <span className="text-[11px] font-semibold leading-tight text-[#f1f5f9]">
              {top_pick.product.name ?? "Mejor alternativa"}
            </span>
            {top_pick.product.brand && (
              <span className="text-[10px] text-[#475569]">{top_pick.product.brand}</span>
            )}
            <span className="text-[20px] font-extrabold leading-none text-[#22c55e]">
              {top_pick.product.clean_score}
            </span>
            {has_biomarkers ? (
              <span className="text-[10px] text-[#22c55e]">
                {top_pick.biomarker_conflicts.length === 0
                  ? "0 conflictos"
                  : `${top_pick.biomarker_conflicts.length} conflicto${top_pick.biomarker_conflicts.length !== 1 ? "s" : ""}`}
              </span>
            ) : (
              <span className="text-[10px] text-[#475569]">Sin biomarcadores</span>
            )}
          </div>
        </div>

        {/* fila delta — solo si delta > 0 */}
        {delta > 0 && (
          <div
            className="flex items-center gap-3 rounded-[10px] border px-4 py-3"
            style={{ background: "rgba(34,197,94,.07)", borderColor: "rgba(34,197,94,.15)" }}
          >
            <span className="text-[22px] font-extrabold text-[#22c55e]">+{delta} pts</span>
            <span className="flex-1 text-[11px] leading-tight text-[#4ade80]">
              mejora en<br />clean score
            </span>
            <span
              className="rounded-full px-3 py-1 text-[11px] font-bold"
              style={{ background: "rgba(96,165,250,.12)", color: "#60a5fa" }}
            >
              {top_pick.compatibility_pct}% tú
            </span>
          </div>
        )}

        {/* ingredientes limpios */}
        {top_pick.clean_ingredients.length > 0 && (
          <div className="flex flex-col gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-[.1em] text-[#334155]">
              Ingredientes sin conflicto
            </span>
            <div className="flex flex-wrap gap-1.5">
              {top_pick.clean_ingredients.slice(0, 6).map((ing) => (
                <span
                  key={ing}
                  className="rounded-[6px] px-2 py-0.5 text-[10px] font-medium"
                  style={{ background: "rgba(34,197,94,.1)", color: "#4ade80" }}
                >
                  {ing}
                </span>
              ))}
              {top_pick.clean_ingredients.length > 6 && (
                <span
                  className="rounded-[6px] border px-2 py-0.5 text-[10px]"
                  style={{ borderColor: "rgba(255,255,255,.08)", color: "#64748b" }}
                >
                  +{top_pick.clean_ingredients.length - 6} más
                </span>
              )}
            </div>
          </div>
        )}

        {/* banner biomarcadores — solo si has_biomarkers */}
        {has_biomarkers && (
          <div
            className="flex items-start gap-2 rounded-[10px] border px-3 py-2.5"
            style={{ background: "rgba(34,197,94,.04)", borderColor: "rgba(34,197,94,.15)" }}
          >
            <span className="mt-0.5 flex-shrink-0 text-[14px] text-[#22c55e]">○</span>
            <div>
              <p className="text-[11px] font-semibold text-[#22c55e]">
                Sin conflictos con tus biomarcadores
              </p>
              {top_pick.biomarker_conflicts.length > 0 && (
                <p className="mt-0.5 text-[10px] leading-snug text-[#475569]">
                  vs. {top_pick.biomarker_conflicts.join(", ")} en el producto escaneado
                </p>
              )}
            </div>
          </div>
        )}

        {/* BioSync CTA — solo si no hay biomarcadores */}
        {!has_biomarkers && (
          <div
            className="flex items-center gap-2 rounded-[10px] border px-3 py-2.5"
            style={{ background: "rgba(255,255,255,.03)", borderColor: "rgba(255,255,255,.07)" }}
          >
            <span className="text-[10px] text-[#475569]">
              Activa BioSync para ver compatibilidad personalizada
            </span>
          </div>
        )}
      </div>
    </aside>
  );
}
