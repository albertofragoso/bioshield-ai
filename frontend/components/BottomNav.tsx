"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Camera, Clock, Activity } from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Home", Icon: Home },
  { href: "/scan", label: "Scan", Icon: Camera },
  { href: "/history", label: "Historial", Icon: Clock },
  { href: "/biosync", label: "Biosync", Icon: Activity },
] as const;

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="bottom navigation"
      className="fixed bottom-0 left-0 right-0 z-20 md:hidden flex items-center justify-around h-14 shrink-0"
      style={{
        background: "rgba(13,19,16,0.95)",
        borderTop: "1px solid rgba(74,222,128,0.1)",
        backdropFilter: "blur(12px)",
      }}
    >
      {NAV_ITEMS.map(({ href, label, Icon }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className="flex flex-col items-center gap-0.5 py-1 px-3 transition-opacity"
            style={{ opacity: active ? 1 : 0.4 }}
          >
            <Icon
              size={18}
              className={active ? "text-brand-green" : "text-subtext"}
              style={active ? { filter: "drop-shadow(0 0 5px rgba(74,222,128,0.6))" } : {}}
            />
            <span
              className="font-mono text-[9px] uppercase tracking-[0.06em]"
              style={{ color: active ? "var(--brand-green)" : "var(--subtext)" }}
            >
              {label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
