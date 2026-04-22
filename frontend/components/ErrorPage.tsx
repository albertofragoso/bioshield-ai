"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";

interface ErrorPageProps {
  onRetry?: () => void;
}

export function ErrorPage({ onRetry }: ErrorPageProps) {
  const router = useRouter();

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-56px)] gap-6 px-6 relative z-10">
      <Image
        src="/avatars/support.png"
        alt=""
        aria-hidden
        width={120}
        height={120}
        className="object-contain"
      />

      <div className="flex flex-col items-center gap-2 text-center">
        <p className="font-sans font-bold text-2xl text-foreground">
          algo salió mal.
        </p>
        <p className="font-mono text-[13px] text-subtext max-w-xs leading-relaxed">
          Intentamos pero no pudimos. Puedes reintentar o volver al inicio.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 w-full max-w-[280px]">
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex-1 rounded-button py-[13px] font-mono text-[12px] font-semibold uppercase tracking-[0.1em] text-brand-green bs-glow-green hover:bs-glow-green-strong transition-all duration-200"
            style={{
              background: "rgba(74,222,128,.15)",
              border: "1.5px solid #4ADE80",
            }}
          >
            reintentar
          </button>
        )}
        <button
          onClick={() => router.push("/")}
          className="flex-1 rounded-button py-[13px] font-mono text-[12px] font-semibold uppercase tracking-[0.1em] text-subtext hover:text-foreground transition-colors"
          style={{ border: "1.5px solid rgba(74,222,128,.3)" }}
        >
          ir al inicio
        </button>
      </div>
    </div>
  );
}
