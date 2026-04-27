"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { logout } from "@/lib/api/auth";
import { useAuthStore } from "@/lib/stores/auth";
import { SessionExpiredDialog } from "@/components/SessionExpiredDialog";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { logout: clearStore } = useAuthStore();
  const [sessionExpired, setSessionExpired] = useState(false);

  // Escucha el evento emitido por client.ts cuando el refresh falla
  useEffect(() => {
    const handler = () => setSessionExpired(true);
    window.addEventListener("session-expired", handler);
    return () => window.removeEventListener("session-expired", handler);
  }, []);

  function handleSessionExpiredConfirm() {
    clearStore();
    window.location.href = "/login";
  }

  async function handleLogout() {
    try {
      await logout();
    } catch {
      // Ignorar si la sesión ya expiró en el servidor
    }
    clearStore();
    router.push("/login");
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header
        className="sticky top-0 z-20 flex items-center justify-between px-4 sm:px-6 h-14 shrink-0"
        style={{
          background: "#0D1310",
          borderBottom: "1px solid rgba(74,222,128,0.1)",
        }}
      >
        {/* Wordmark compacto */}
        <Link
          href="/"
          className="flex items-baseline gap-[5px] hover:opacity-80 transition-opacity"
        >
          <span
            className="font-display text-[20px] text-brand-green"
            style={{
              textShadow:
                "0 0 8px rgba(74,222,128,.8), 0 0 22px rgba(74,222,128,.45), 0 0 48px rgba(74,222,128,.18)",
              animation: "bs-wordmark-green-kf 3s ease-in-out infinite",
            }}
          >
            BioShield
          </span>
          <span
            className="font-sans font-bold text-[18px] text-brand-amber tracking-[0.06em]"
            style={{
              textShadow:
                "0 0 8px rgba(245,158,11,.8), 0 0 22px rgba(245,158,11,.4)",
              animation: "bs-wordmark-amber-kf 3s ease-in-out infinite",
              animationDelay: "0.4s",
            }}
          >
            AI
          </span>
        </Link>

        {/* User actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 font-mono text-[11px] text-subtext hover:text-foreground transition-colors uppercase tracking-[0.08em]"
            title="Cerrar sesión"
          >
            <LogOut size={13} />
            salir
          </button>
        </div>
      </header>

      <main className="flex-1 relative z-10">{children}</main>

      <SessionExpiredDialog open={sessionExpired} onConfirm={handleSessionExpiredConfirm} />
    </div>
  );
}
