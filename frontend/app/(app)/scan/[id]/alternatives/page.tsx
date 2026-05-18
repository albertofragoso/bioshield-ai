"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { useEffect } from "react";
import { getAlternatives } from "@/lib/api/scan";
import { recordAnalyticsEvent } from "@/lib/api/analytics";
import { AILoadingState, ALTERNATIVES_PHASES } from "@/components/AILoadingState";
import { AlternativesHeroPanel } from "@/components/AlternativesHeroPanel";
import { AlternativesRankingList } from "@/components/AlternativesRankingList";
import { AvatarGlow } from "@/components/AvatarGlow";
import type { AlternativesResponse } from "@/lib/api/types";

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-4 py-16 px-4 text-center">
      <AvatarGlow variant="gray" size={80} intensity="soft" />
      <p className="text-[15px] font-semibold text-[#94a3b8]">
        No encontramos alternativas en nuestra base de datos aún
      </p>
      <p className="text-[12px] text-[#475569]">Estamos expandiendo el catálogo</p>
    </div>
  );
}

function SkeletonTopPick() {
  return (
    <div className="rounded-[14px] border border-[#1a2318] bg-[#0b150b] overflow-hidden animate-pulse">
      <div className="h-8 bg-[#1a2318]" />
      <div className="flex gap-3 p-4">
        <div className="w-[88px] h-[88px] rounded-full bg-[#1a2318] shrink-0" />
        <div className="flex-1 space-y-2 pt-2">
          <div className="h-4 bg-[#1a2318] rounded w-3/4" />
          <div className="h-3 bg-[#1a2318] rounded w-1/2" />
          <div className="h-3 bg-[#1a2318] rounded w-2/3" />
        </div>
      </div>
      <div className="h-8 bg-[#1a2318] mx-4 mb-4 rounded-lg" />
    </div>
  );
}

function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 px-3 py-2.5 rounded-[10px] border border-[#1a2318] bg-[#0b150b] animate-pulse">
      <div className="w-10 h-10 rounded-full bg-[#1a2318] shrink-0" />
      <div className="flex-1 space-y-1.5">
        <div className="h-3 bg-[#1a2318] rounded w-3/4" />
        <div className="h-2.5 bg-[#1a2318] rounded w-1/2" />
      </div>
      <div className="w-16 h-5 bg-[#1a2318] rounded-full" />
    </div>
  );
}

export default function AlternativesPage() {
  const { id: barcode } = useParams<{ id: string }>();
  const router = useRouter();

  const { data, isLoading, isError } = useQuery<AlternativesResponse>({
    queryKey: ["alternatives", barcode],
    queryFn: () => getAlternatives(barcode),
    staleTime: 10 * 60 * 1000,
  });

  useEffect(() => {
    recordAnalyticsEvent({ event_type: "alt_page_opened", payload: { barcode } });
  }, [barcode]);

  const isEmpty = data && !data.top_pick && data.alternatives.length === 0;

  return (
    <div className="relative z-10 py-6 mx-auto w-full max-w-[480px] px-4 md:max-w-[1080px] md:px-8 flex flex-col gap-5">
      {/* Back nav */}
      <Link
        href={`/scan/${barcode}`}
        className="inline-flex items-center gap-1.5 font-mono text-[11px] text-[#4a5568] hover:text-foreground transition-colors uppercase tracking-[0.08em] -mb-2"
      >
        <ArrowLeft size={13} />
        resultado del scan
      </Link>

      {/* Header */}
      <div>
        <h1 className="text-[22px] font-bold text-[#f1f5f9]">Alternativas más limpias</h1>
        {data && (
          <p className="text-[12px] text-[#475569] mt-0.5">
            Para: {data.scanned_product.name || barcode}
            {data.fallback_used && (
              <span className="ml-2 text-[#64748b]">· Resultados aproximados</span>
            )}
          </p>
        )}
      </div>

      {/* Loading */}
      {isLoading && (
        <>
          <AILoadingState phases={ALTERNATIVES_PHASES} />
          <SkeletonTopPick />
          <SkeletonRow />
          <SkeletonRow />
        </>
      )}

      {/* Error */}
      {isError && (
        <div className="text-center py-10 text-[#f87171] text-[14px]">
          Error al cargar alternativas.{" "}
          <button onClick={() => router.refresh()} className="underline">
            Reintentar
          </button>
        </div>
      )}

      {/* Empty */}
      {!isLoading && isEmpty && <EmptyState />}

      {/* Results — layout two-column en desktop, single-column en mobile */}
      {data && !isEmpty && (
        <div className="flex flex-col gap-5 md:grid md:gap-7" style={{ gridTemplateColumns: "380px 1fr" }}>
          <AlternativesHeroPanel data={data} />
          {data.alternatives.length > 0 ? (
            <AlternativesRankingList
              alternatives={data.alternatives}
              fallbackUsed={data.fallback_used}
            />
          ) : (
            <div className="flex flex-col items-center gap-4 py-12 text-center">
              <AvatarGlow variant="gray" size={80} intensity="soft" />
              <p className="text-[14px] text-[#64748b]">
                No encontramos alternativas en esta categoría
              </p>
              {!data.has_biomarkers && (
                <p className="text-[12px] text-[#475569]">
                  Activa BioSync para personalización completa
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
