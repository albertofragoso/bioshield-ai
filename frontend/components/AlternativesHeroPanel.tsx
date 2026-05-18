import { AlternativesResponse } from "@/lib/api/types";
import { AvatarGlow } from "@/components/AvatarGlow";

const SEMAPHORE_LABEL: Record<string, string> = {
  BLUE:   "Óptimo",
  YELLOW: "Aceptable",
  ORANGE: "Riesgo",
  RED:    "Evitar",
  GRAY:   "Sin datos",
};

interface AlternativesHeroPanelProps {
  data: AlternativesResponse;
}

export function AlternativesHeroPanel({ data }: AlternativesHeroPanelProps) {
  const { scanned_product, top_pick, has_biomarkers } = data;

  if (!top_pick) return null;

  const delta = top_pick.product.clean_score - scanned_product.clean_score;
  const scoreWidth = Math.min(100, Math.max(0, top_pick.product.clean_score));

  return (
    <aside className="sticky flex flex-col gap-4" style={{ top: "72px" }}>
      <span className="text-[10px] font-semibold uppercase tracking-[.1em] text-[#334155]">
        Mejor alternativa
      </span>

      <div
        className="flex flex-col gap-5 rounded-[18px] border p-5"
        style={{
          background: "linear-gradient(145deg, rgba(12,24,40,.7) 0%, rgba(8,14,8,.5) 100%)",
          borderColor: "rgba(34,197,94,.2)",
          boxShadow: "0 0 24px rgba(34,197,94,.08)",
        }}
      >
        {/* Sección 1 — Hero del producto */}
        <div className="flex flex-col items-center gap-3 text-center">
          <AvatarGlow
            variant={top_pick.avatar_variant}
            size={80}
            intensity="strong"
          />
          <div className="flex flex-col gap-0.5">
            <span className="text-[14px] font-bold leading-snug text-[#f1f5f9]">
              {top_pick.product.name ?? "Mejor alternativa"}
            </span>
            {top_pick.product.brand && (
              <span className="text-[11px] text-[#475569]">{top_pick.product.brand}</span>
            )}
          </div>
        </div>

        {/* Sección 2 — Score con contexto visual */}
        <div className="flex flex-col items-center gap-2">
          <div className="flex items-end gap-1.5 leading-none">
            <span className="text-[48px] font-extrabold leading-none text-[#22c55e]">
              {top_pick.product.clean_score}
            </span>
            <span className="mb-2 text-[16px] font-medium text-[#334155]">/ 100</span>
          </div>
          <span
            className="rounded-full px-3 py-0.5 text-[10px] font-bold uppercase tracking-[.08em]"
            style={{ background: "rgba(34,197,94,.12)", color: "#22c55e", border: "1px solid rgba(34,197,94,.3)" }}
          >
            {SEMAPHORE_LABEL.BLUE}
          </span>
          {/* barra de progreso */}
          <div className="w-full rounded-full" style={{ height: "4px", background: "rgba(255,255,255,.08)" }}>
            <div
              className="rounded-full"
              style={{ height: "4px", width: `${scoreWidth}%`, background: "#22c55e", transition: "width 0.5s ease" }}
            />
          </div>
          {/* delta vs escaneado */}
          {delta > 0 && (
            <span className="text-[11px] font-medium" style={{ color: "#4ade80" }}>
              ↑ +{delta} pts vs tu producto escaneado
            </span>
          )}
        </div>

        {/* Sección 3 — Compatibilidad (solo si has_biomarkers) */}
        {has_biomarkers && (
          <div
            className="flex flex-col gap-3 rounded-[12px] border p-4"
            style={{ background: "rgba(96,165,250,.05)", borderColor: "rgba(96,165,250,.18)" }}
          >
            <div className="flex items-center gap-3">
              <div className="flex flex-col">
                <span className="text-[28px] font-extrabold leading-none text-[#60a5fa]">
                  {top_pick.compatibility_pct}%
                </span>
                <span className="text-[10px] text-[#475569]">compatible con tu perfil</span>
              </div>
              {top_pick.biomarker_conflicts.length === 0 && (
                <span
                  className="ml-auto rounded-full px-3 py-1 text-[10px] font-bold"
                  style={{ background: "rgba(34,197,94,.12)", color: "#22c55e", border: "1px solid rgba(34,197,94,.25)" }}
                >
                  Sin conflictos
                </span>
              )}
            </div>
            {top_pick.biomarker_conflicts.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <span className="text-[9px] font-semibold uppercase tracking-[.08em] text-[#f87171]">
                  Conflictos
                </span>
                <div className="flex flex-wrap gap-1">
                  {top_pick.biomarker_conflicts.map((conflict) => (
                    <span
                      key={conflict}
                      className="rounded-[5px] px-2 py-0.5 text-[10px] font-medium"
                      style={{ background: "rgba(248,113,113,.1)", color: "#f87171" }}
                    >
                      {conflict}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Sección 4 — Ingredientes limpios */}
        {top_pick.clean_ingredients.length > 0 && (
          <div className="flex flex-col gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-[.1em] text-[#334155]">
              Ingredientes sin conflicto
            </span>
            <div className="flex flex-wrap gap-1.5">
              {top_pick.clean_ingredients.map((ing) => (
                <span
                  key={ing}
                  className="rounded-[6px] px-2 py-0.5 text-[10px] font-medium"
                  style={{ background: "rgba(34,197,94,.1)", color: "#4ade80" }}
                >
                  {ing}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* CTA BioSync — solo si no hay biomarcadores */}
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
