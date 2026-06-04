"use client";

import type { ScanHistoryEntry } from "@/lib/api/types";
import { useBiomarkerStatus } from "@/hooks/use-biosync";
import { useScanHistory } from "@/hooks/use-scan";
import { HomeOrbSection } from "@/components/home/HomeOrbSection";
import { HomeStatsPanel } from "@/components/home/HomeStatsPanel";

export default function DashboardPage() {
  const biosyncQuery = useBiomarkerStatus();

  const historyQuery = useScanHistory(5);

  const historyItems: ScanHistoryEntry[] = historyQuery.data ?? [];
  const historyEmpty =
    !historyQuery.isLoading && !historyQuery.isError && historyItems.length === 0;

  return (
    <div className="relative z-10 flex flex-col md:grid md:grid-cols-[40%_60%] md:min-h-[calc(100vh-56px)]">
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
