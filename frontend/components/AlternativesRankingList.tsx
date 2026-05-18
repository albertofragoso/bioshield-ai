import { AlternativeItem } from "@/lib/api/types";
import { AlternativesRankingRow } from "@/components/AlternativesRankingRow";

interface AlternativesRankingListProps {
  alternatives: AlternativeItem[];
  fallbackUsed: boolean;
}

export function AlternativesRankingList({
  alternatives,
  fallbackUsed,
}: AlternativesRankingListProps) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-baseline gap-3">
        <span className="text-[10px] font-semibold uppercase tracking-[.1em] text-[#334155]">
          Ranking por clean score
        </span>
        <span className="ml-auto text-[11px] text-[#334155]">
          {alternatives.length} alternativa{alternatives.length !== 1 ? "s" : ""}
        </span>
      </div>
      <div className="flex flex-col gap-2">
        {alternatives.map((item, idx) => (
          <AlternativesRankingRow
            key={item.product.barcode}
            item={item}
            position={idx + 1}
          />
        ))}
      </div>
      {fallbackUsed && (
        <p className="rounded-[10px] border border-[rgba(255,255,255,.06)] bg-[rgba(255,255,255,.03)] px-4 py-3 text-[11px] text-[#475569]">
          ⓘ Resultados basados en categoría general · Activa BioSync para personalización completa
        </p>
      )}
    </section>
  );
}
