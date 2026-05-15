import Link from "next/link";
import { Activity, AlertTriangle, History, ChevronRight } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { SemaphoreBadge } from "@/components/semaphore/SemaphoreBadge";
import type { ScanHistoryEntry } from "@/lib/api/types";

interface BiosyncData {
  has_data: boolean;
  expires_at?: string;
}

interface HomeStatsPanelProps {
  biosyncData: BiosyncData | undefined;
  biosyncLoading: boolean;
  historyItems: ScanHistoryEntry[];
  historyEmpty: boolean;
  historyLoading: boolean;
}

export function HomeStatsPanel({
  biosyncData,
  biosyncLoading,
  historyItems,
  historyEmpty,
  historyLoading,
}: HomeStatsPanelProps) {
  const hasData = biosyncData?.has_data === true;
  const expiresAt = biosyncData?.expires_at;
  const daysLeft = expiresAt
    ? Math.ceil((new Date(expiresAt).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : null;
  const nearExpiry = daysLeft !== null && daysLeft < 30;

  return (
    <div className="flex flex-col gap-4 px-4 py-5 md:justify-center md:px-6">
      {/* Stats pills */}
      <div className="flex gap-3 animate-fade-up" style={{ animationDelay: "0.05s" }}>
        <div className="bs-card flex-1 px-4 py-3 text-center">
          <p className="font-mono font-bold text-2xl text-brand-green">{historyItems.length}</p>
          <p className="font-mono text-[9px] uppercase tracking-[0.06em] text-subtext mt-0.5">
            Recientes
          </p>
        </div>
        <div className="bs-card flex-1 px-4 py-3 text-center">
          {biosyncLoading ? (
            <Skeleton className="h-7 w-12 mx-auto mb-1" />
          ) : daysLeft !== null ? (
            <p className="font-mono font-bold text-2xl text-brand-amber">{daysLeft}d</p>
          ) : (
            <p className="font-mono font-bold text-2xl text-subtext">—</p>
          )}
          <p className="font-mono text-[9px] uppercase tracking-[0.06em] text-subtext mt-0.5">
            Biomarcadores
          </p>
        </div>
      </div>

      {/* Biosync card */}
      <Link
        href="/biosync"
        className="bs-card block px-4 py-3 hover:border-brand-green/30 transition-all group animate-fade-up"
        style={{ animationDelay: "0.15s" }}
      >
        {biosyncLoading ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-3 w-40" />
            <Skeleton className="h-3 w-56" />
          </div>
        ) : hasData && daysLeft !== null ? (
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Activity size={14} className="text-brand-green" />
                <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-brand-green">
                  Biomarcadores activos
                </span>
                {nearExpiry && (
                  <span
                    className="font-mono text-[9px] px-1.5 py-0.5 rounded-full"
                    style={{
                      background: "rgba(245,158,11,.12)",
                      border: "1px solid rgba(245,158,11,.3)",
                      color: "#F59E0B",
                    }}
                  >
                    <AlertTriangle size={8} className="inline mr-0.5" />
                    {daysLeft}d
                  </span>
                )}
              </div>
              <p className="font-sans text-xs text-subtext">
                Expira en {daysLeft} día{daysLeft !== 1 ? "s" : ""}
              </p>
            </div>
            <ChevronRight
              size={16}
              className="text-subtext opacity-60 group-hover:translate-x-0.5 transition-transform"
            />
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Activity size={14} className="text-subtext" />
                <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-subtext">
                  Biomarcadores
                </span>
              </div>
              <p className="font-sans text-xs text-subtext">
                Sube tu panel de sangre para alertas personalizadas
              </p>
            </div>
            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-brand-green shrink-0">
              Subir →
            </span>
          </div>
        )}
      </Link>

      {/* Historial reciente */}
      <div className="bs-card px-4 py-3 animate-fade-up" style={{ animationDelay: "0.25s" }}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <History size={13} className="text-subtext" />
            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-subtext">
              Escaneados recientemente
            </span>
          </div>
          {!historyEmpty && (
            <Link
              href="/history"
              className="font-mono text-[10px] text-brand-green hover:opacity-70 transition-opacity"
            >
              Ver todo →
            </Link>
          )}
        </div>

        {historyLoading ? (
          <div className="flex flex-col gap-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="rounded-full shrink-0 w-8 h-8" />
                <div className="flex-1 flex flex-col gap-1.5">
                  <Skeleton className="h-3 w-3/4" />
                  <Skeleton className="h-2.5 w-1/3" />
                </div>
              </div>
            ))}
          </div>
        ) : historyEmpty ? (
          <p className="font-mono text-[10px] text-subtext py-4 text-center">
            Escanea tu primer producto para empezar.
          </p>
        ) : (
          <div className="flex flex-col">
            {historyItems.map((item, i) => (
              <HistoryRow
                key={item.id}
                item={item}
                last={i === historyItems.length - 1}
                index={i}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function HistoryRow({
  item,
  last,
  index,
}: {
  item: ScanHistoryEntry;
  last: boolean;
  index: number;
}) {
  return (
    <Link
      href={`/scan/${item.product_barcode}`}
      className="flex items-center gap-3 py-2.5 hover:bg-brand-green/[0.03] transition-colors -mx-2 px-2 rounded animate-stagger-in"
      style={{
        ...(last ? {} : { borderBottom: "1px solid rgba(74,222,128,.06)" }),
        animationDelay: `${index * 0.1}s`,
      }}
    >
      <SemaphoreBadge color={item.semaphore} size={32} />
      <div className="flex-1 min-w-0">
        <p className="font-sans text-sm text-foreground truncate">
          {item.product_name ?? item.product_barcode}
        </p>
        <p className="font-mono text-[10px] text-subtext mt-0.5">
          {relativeTime(item.scanned_at)} · {item.source === "photo" ? "Foto" : "Barcode"}
        </p>
      </div>
      <ChevronRight size={14} className="text-subtext shrink-0 opacity-60" />
    </Link>
  );
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 0) return "Ahora";
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Ahora";
  if (mins < 60) return `hace ${mins}min`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `hace ${hrs}h`;
  return `hace ${Math.floor(hrs / 24)}d`;
}
