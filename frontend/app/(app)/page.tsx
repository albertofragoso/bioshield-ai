"use client";

import { useQuery } from "@tanstack/react-query";
import { getBiomarkerStatus } from "@/lib/api/biosync";
import { getScanHistory } from "@/lib/api/scan";
import { HttpError } from "@/lib/api/client";
import type { ScanHistoryEntry } from "@/lib/api/types";
import { HomeOrbSection } from "@/components/home/HomeOrbSection";
import { HomeStatsPanel } from "@/components/home/HomeStatsPanel";

export default function DashboardPage() {
  const biosyncQuery = useQuery({
    queryKey: ["biosync-status"],
    queryFn: getBiomarkerStatus,
    retry: (count, err) => !(err instanceof HttpError && err.status === 404),
    staleTime: 5 * 60 * 1000,
  });

  const historyQuery = useQuery({
    queryKey: ["scan-history", 5],
    queryFn: () => getScanHistory(5),
    retry: false,
    staleTime: 60 * 1000,
  });

  const historyItems: ScanHistoryEntry[] = historyQuery.data ?? [];
  const historyEmpty =
    !historyQuery.isLoading && !historyQuery.isError && historyItems.length === 0;

  return (
    <div className="relative z-10 flex flex-col md:grid md:grid-cols-2 md:min-h-[calc(100vh-56px)]">
      <HomeOrbSection className="pt-8 pb-6 px-6 md:border-r md:border-brand-green/[0.06] md:bg-[radial-gradient(ellipse_70%_60%_at_50%_50%,rgba(74,222,128,0.04)_0%,transparent_70%)]" />
      <HomeStatsPanel
        biosyncData={biosyncQuery.data}
        biosyncLoading={biosyncQuery.isLoading}
        historyItems={historyItems}
        historyEmpty={historyEmpty}
        historyLoading={historyQuery.isLoading}
      />
    </div>
  );
}
