"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import Image from "next/image";
import { ArrowLeft, Search, ChevronRight } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { SemaphoreBadge } from "@/components/semaphore/SemaphoreBadge";
import { getScanHistory } from "@/lib/api/scan";
import type { ScanHistoryEntry, SemaphoreColor } from "@/lib/api/types";

type FilterTab = "all" | SemaphoreColor;

const FILTER_TABS: Array<{ id: FilterTab; label: string; color?: string }> = [
  { id: "all",    label: "Todos"   },
  { id: "RED",    label: "RED",    color: "#F87171" },
  { id: "ORANGE", label: "ORANGE", color: "#FB923C" },
  { id: "YELLOW", label: "YELLOW", color: "#FACC15" },
  { id: "BLUE",   label: "BLUE",   color: "#60A5FA" },
  { id: "GRAY",   label: "GRAY",   color: "#A8B3A7" },
];

function hexToRgb(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `${r},${g},${b}`;
}

/* ── Day label ────────────────────────────────────────────── */

function dayLabel(iso: string): string {
  const date = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();

  if (sameDay(date, today)) return "Hoy";
  if (sameDay(date, yesterday)) return "Ayer";

  const diffDays = Math.floor((today.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays < 7) return `Hace ${diffDays} días`;

  return date.toLocaleDateString("es-MX", { month: "long", year: "numeric" });
}

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

function absoluteDate(iso: string): string {
  return new Date(iso).toLocaleDateString("es-MX", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/* ── Page ─────────────────────────────────────────────────── */

export default function HistoryPage() {
  const [activeFilter, setActiveFilter] = useState<FilterTab>("all");
  const [search, setSearch] = useState("");

  const historyQuery = useQuery({
    queryKey: ["scan-history", 100],
    queryFn: () => getScanHistory(100),
    retry: false,
    staleTime: 60 * 1000,
  });

  const allItems: ScanHistoryEntry[] = historyQuery.data ?? [];

  /* Counts por filtro */
  const counts = useMemo(() => {
    const c: Record<string, number> = { all: allItems.length };
    allItems.forEach(({ semaphore }) => {
      c[semaphore] = (c[semaphore] ?? 0) + 1;
    });
    return c;
  }, [allItems]);

  /* Filtrar + buscar */
  const filtered = useMemo(() => {
    let items = allItems;
    if (activeFilter !== "all") {
      items = items.filter((i) => i.semaphore === activeFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      items = items.filter(
        (i) =>
          (i.product_name ?? "").toLowerCase().includes(q) ||
          i.product_barcode.includes(q),
      );
    }
    return items;
  }, [allItems, activeFilter, search]);

  /* Agrupar por día */
  const grouped = useMemo(() => {
    const groups = new Map<string, ScanHistoryEntry[]>();
    filtered.forEach((item) => {
      const label = dayLabel(item.scanned_at);
      if (!groups.has(label)) groups.set(label, []);
      groups.get(label)!.push(item);
    });
    return groups;
  }, [filtered]);

  /* Count de últimos 30 días */
  const last30 = useMemo(() => {
    const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1000;
    return allItems.filter((i) => new Date(i.scanned_at).getTime() > cutoff).length;
  }, [allItems]);

  const isLoading = historyQuery.isLoading;
  const isEmpty = !isLoading && allItems.length === 0;
  const isFilteredEmpty = !isLoading && allItems.length > 0 && filtered.length === 0;

  return (
    <div className="relative z-10 min-h-screen px-4 py-6 max-w-[720px] mx-auto">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 font-mono text-[11px] text-subtext hover:text-foreground transition-colors uppercase tracking-[0.08em] mb-6"
      >
        <ArrowLeft size={13} />
        volver
      </Link>

      <div className="flex items-baseline justify-between mb-1">
        <h1 className="font-sans font-bold text-xl text-foreground">Historial</h1>
        {!isLoading && (
          <span className="font-mono text-[11px] text-subtext uppercase tracking-[0.08em]">
            {last30} en 30 días
          </span>
        )}
      </div>
      <p className="font-mono text-[11px] text-subtext mb-6 uppercase tracking-[0.08em]">
        SCAN HISTORY · TIMELINE
      </p>

      {/* ── Búsqueda ── */}
      <div className="relative mb-4">
        <Search
          size={13}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-subtext pointer-events-none"
        />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar por producto o código"
          className="w-full pl-8 pr-3 py-2.5 rounded-input font-mono text-[12px] text-foreground placeholder:text-subtext bg-transparent outline-none transition-all bs-input-focus"
          style={{ border: "1px solid rgba(74,222,128,.15)" }}
        />
      </div>

      {/* ── Filtros ── */}
      {!isLoading && (
        <div className="flex gap-2 flex-wrap mb-6">
          {FILTER_TABS.map(({ id, label, color }) => {
            const isActive = activeFilter === id;
            const count = counts[id] ?? 0;
            const rgb = color ? hexToRgb(color) : null;
            return (
              <button
                key={id}
                onClick={() => setActiveFilter(id)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full font-mono text-[11px] uppercase tracking-[0.06em] transition-all"
                style={{
                  border: `1px solid ${isActive ? (color ?? "rgba(74,222,128,.5)") : "rgba(74,222,128,.12)"}`,
                  background: isActive
                    ? rgb
                      ? `rgba(${rgb},.12)`
                      : "rgba(74,222,128,.10)"
                    : "transparent",
                  color: isActive ? (color ?? "#4ADE80") : "#6B8A6A",
                }}
              >
                {label}
                <span
                  className="px-1.5 py-0.5 rounded-full text-[10px]"
                  style={{
                    background: rgb ? `rgba(${rgb},.15)` : "rgba(74,222,128,.12)",
                    color: color ?? "#4ADE80",
                  }}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* ── Content ── */}
      {isLoading ? (
        <LoadingSkeletons />
      ) : isEmpty ? (
        <EmptyState />
      ) : isFilteredEmpty ? (
        <p className="font-mono text-[12px] text-subtext py-8 text-center uppercase tracking-[0.08em]">
          Sin resultados para este filtro.
        </p>
      ) : (
        <div className="flex flex-col gap-6">
          {Array.from(grouped.entries()).map(([label, items]) => (
            <div key={label}>
              <p
                className="font-mono text-[10px] uppercase tracking-[0.12em] mb-2 pb-1"
                style={{
                  color: "#6B8A6A",
                  borderBottom: "1px solid rgba(74,222,128,.06)",
                }}
              >
                {label}
              </p>
              <div className="flex flex-col">
                {items.map((item, i) => (
                  <HistoryItemRow
                    key={item.id}
                    item={item}
                    last={i === items.length - 1}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Sub-components ───────────────────────────────────────── */

function HistoryItemRow({ item, last }: { item: ScanHistoryEntry; last: boolean }) {
  return (
    <Link
      href={`/scan/${item.product_barcode}`}
      className="flex items-center gap-3 py-3 -mx-2 px-2 rounded transition-colors"
      style={{
        borderBottom: last ? "none" : "1px solid rgba(74,222,128,.08)",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(74,222,128,.04)")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
    >
      <SemaphoreBadge color={item.semaphore} size={40} />
      <div className="flex-1 min-w-0">
        <p className="font-sans text-sm text-foreground truncate">
          {item.product_name ?? "Producto sin nombre"}
        </p>
        <div className="flex items-center gap-2 mt-0.5">
          <span
            className="font-mono text-[10px] text-subtext"
            title={absoluteDate(item.scanned_at)}
          >
            {relativeTime(item.scanned_at)}
          </span>
          <span className="text-subtext/40">·</span>
          <span
            className="font-mono text-[10px] px-1.5 py-0.5 rounded-full"
            style={{
              background: "rgba(74,222,128,.06)",
              border: "1px solid rgba(74,222,128,.1)",
              color: "#6B8A6A",
            }}
          >
            {item.source === "photo" ? "Foto" : "Barcode"}
          </span>
        </div>
      </div>
      <ChevronRight size={16} className="text-subtext shrink-0 opacity-60" />
    </Link>
  );
}

function LoadingSkeletons() {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 py-2">
          <Skeleton className="rounded-full shrink-0" style={{ width: 40, height: 40 }} />
          <div className="flex-1 flex flex-col gap-1.5">
            <Skeleton className="h-3 w-3/5" />
            <Skeleton className="h-2.5 w-1/4" />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-5 py-16 text-center">
      <div className="bs-mascot-glow">
        <Image
          src="/avatars/welcome.png"
          alt=""
          aria-hidden
          width={120}
          height={120}
          className="object-contain animate-pulse-glow"
          priority
        />
      </div>
      <div>
        <p className="font-sans text-sm text-foreground">Sin escaneos aún</p>
        <p className="font-mono text-[11px] text-subtext mt-1">
          Escanea tu primer producto para empezar.
        </p>
      </div>
      <Link
        href="/scan"
        className="px-6 py-3 rounded-button font-mono text-[12px] uppercase tracking-[0.08em] text-brand-green transition-all"
        style={{
          background: "rgba(74,222,128,.12)",
          border: "1px solid rgba(74,222,128,.3)",
        }}
      >
        Escanear producto →
      </Link>
    </div>
  );
}
