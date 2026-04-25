"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import Image from "next/image";
import { Camera, Activity, History, ChevronRight, AlertTriangle } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { SemaphoreBadge } from "@/components/semaphore/SemaphoreBadge";
import { getBiomarkerStatus } from "@/lib/api/biosync";
import { getScanHistory } from "@/lib/api/scan";
import { HttpError } from "@/lib/api/client";
import type { ScanHistoryEntry } from "@/lib/api/types";

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

  const hasData = biosyncQuery.data?.has_data === true;
  const expiresAt = biosyncQuery.data?.expires_at;
  const daysLeft = expiresAt
    ? Math.ceil((new Date(expiresAt).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : null;
  const nearExpiry = daysLeft !== null && daysLeft < 30;

  const historyItems: ScanHistoryEntry[] = historyQuery.data ?? [];
  const historyEmpty = !historyQuery.isLoading && historyItems.length === 0;

  return (
    <div className="relative z-10 min-h-screen px-4 py-6 max-w-[640px] mx-auto">
      {/* ── Hero CTA ── */}
      <Link
        href="/scan"
        className="bs-card block px-6 py-6 mb-4 bs-glow-green hover:bs-glow-green-strong transition-all group"
      >
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Camera size={18} className="text-brand-green" />
              <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-brand-green">
                Escanear producto
              </span>
            </div>
            <p className="font-sans text-sm text-subtext">
              Barcode · foto de etiqueta · análisis IA
            </p>
          </div>
          <ChevronRight
            size={20}
            className="text-brand-green opacity-60 group-hover:translate-x-0.5 transition-transform"
          />
        </div>
      </Link>

      {/* ── Biosync card ── */}
      <Link
        href="/biosync"
        className="bs-card block px-6 py-5 mb-4 hover:border-brand-green/30 transition-all group"
      >
        {biosyncQuery.isLoading ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-3 w-40" />
            <Skeleton className="h-3 w-56" />
          </div>
        ) : hasData && daysLeft !== null ? (
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Activity size={16} className="text-brand-green" />
                <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-brand-green">
                  Biomarcadores activos
                </span>
                {nearExpiry && (
                  <span
                    className="font-mono text-[10px] px-1.5 py-0.5 rounded-full"
                    style={{
                      background: "rgba(245,158,11,.12)",
                      border: "1px solid rgba(245,158,11,.3)",
                      color: "#F59E0B",
                    }}
                  >
                    <AlertTriangle size={9} className="inline mr-0.5" />
                    {daysLeft}d
                  </span>
                )}
              </div>
              <p className="font-sans text-sm text-subtext">
                Expira en {daysLeft} día{daysLeft !== 1 ? "s" : ""}
              </p>
            </div>
            <ChevronRight
              size={18}
              className="text-subtext group-hover:text-foreground opacity-60 group-hover:translate-x-0.5 transition-all"
            />
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Activity size={16} className="text-subtext" />
                <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-subtext">
                  Biomarcadores
                </span>
              </div>
              <p className="font-sans text-sm text-subtext">
                Sube tu panel de sangre para alertas personalizadas
              </p>
            </div>
            <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-brand-green shrink-0">
              Subir →
            </span>
          </div>
        )}
      </Link>

      {/* ── Recent scans ── */}
      <div className="bs-card px-6 py-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <History size={15} className="text-subtext" />
            <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-subtext">
              Escaneados recientemente
            </span>
          </div>
          {!historyEmpty && (
            <Link
              href="/history"
              className="font-mono text-[11px] text-brand-green hover:opacity-70 transition-opacity"
            >
              Ver todo →
            </Link>
          )}
        </div>

        {historyQuery.isLoading ? (
          <div className="flex flex-col gap-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="rounded-full shrink-0" style={{ width: 40, height: 40 }} />
                <div className="flex-1 flex flex-col gap-1.5">
                  <Skeleton className="h-3 w-3/4" />
                  <Skeleton className="h-2.5 w-1/3" />
                </div>
              </div>
            ))}
          </div>
        ) : historyEmpty ? (
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <div className="bs-mascot-glow">
              <Image
                src="/avatars/welcome.png"
                alt=""
                aria-hidden
                width={100}
                height={100}
                className="object-contain animate-pulse-glow"
                priority
              />
            </div>
            <div>
              <p className="font-sans text-sm text-foreground">Sin scans aún</p>
              <p className="font-mono text-[11px] text-subtext mt-1">
                Escanea tu primer producto para empezar.
              </p>
            </div>
            <Link
              href="/scan"
              className="px-5 py-2.5 rounded-button font-mono text-[12px] uppercase tracking-[0.08em] text-brand-green transition-all"
              style={{
                background: "rgba(74,222,128,.12)",
                border: "1px solid rgba(74,222,128,.3)",
              }}
            >
              Escanear producto →
            </Link>
          </div>
        ) : (
          <div className="flex flex-col">
            {historyItems.map((item, i) => (
              <HistoryRow key={item.id} item={item} last={i === historyItems.length - 1} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── HistoryRow (inline — único consumer por ahora) ───────── */

function HistoryRow({ item, last }: { item: ScanHistoryEntry; last: boolean }) {
  return (
    <Link
      href={`/scan/${item.product_barcode}`}
      className="flex items-center gap-3 py-3 hover:bg-brand-green/[0.03] transition-colors -mx-2 px-2 rounded"
      style={last ? {} : { borderBottom: "1px solid rgba(74,222,128,.06)" }}
    >
      <SemaphoreBadge color={item.semaphore} size={40} />
      <div className="flex-1 min-w-0">
        <p className="font-sans text-sm text-foreground truncate">
          {item.product_name ?? item.product_barcode}
        </p>
        <p className="font-mono text-[10.5px] text-subtext mt-0.5">
          {relativeTime(item.scanned_at)} · {item.source === "photo" ? "Foto" : "Barcode"}
        </p>
      </div>
      <ChevronRight size={16} className="text-subtext shrink-0 opacity-60" />
    </Link>
  );
}

/* ── Utilities ────────────────────────────────────────────── */

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Ahora";
  if (mins < 60) return `hace ${mins}min`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `hace ${hrs}h`;
  const days = Math.floor(hrs / 24);
  return `hace ${days}d`;
}
