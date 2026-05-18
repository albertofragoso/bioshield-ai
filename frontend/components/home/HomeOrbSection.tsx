import Link from "next/link";
import Image from "next/image";

interface HomeOrbSectionProps {
  className?: string;
}

const PARTICLES = [
  { size: 3, top: "22%", left: "12%", delay: "0s", duration: "3.2s" },
  { size: 2, top: "35%", left: "85%", delay: "0.5s", duration: "2.6s" },
  { size: 3, top: "68%", left: "16%", delay: "1s", duration: "3.9s" },
  { size: 2, top: "78%", left: "80%", delay: "0.3s", duration: "2.9s" },
  { size: 2, top: "12%", left: "72%", delay: "0.7s", duration: "4.1s" },
] as const;

const DATA_LINES = ["01001101", "ADT:0.82", "E621:⚠", "USDA:OK"] as const;

export function HomeOrbSection({ className }: HomeOrbSectionProps) {
  return (
    <div className={`relative flex flex-col items-center justify-center gap-2 overflow-hidden ${className ?? ""}`}>
      {/* Scan line periódica — usa keyframe scan-line existente en globals.css */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px"
        style={{
          background: "linear-gradient(90deg, transparent, rgba(74,222,128,0.35), transparent)",
          animation: "scan-line 5s ease-in-out infinite",
        }}
      />

      {/* Partículas flotantes */}
      {PARTICLES.map((p, i) => (
        <div
          key={i}
          className="pointer-events-none absolute rounded-full animate-float-p"
          style={{
            width: p.size,
            height: p.size,
            top: p.top,
            left: p.left,
            background: "rgba(74,222,128,0.45)",
            boxShadow: "0 0 4px rgba(74,222,128,0.4)",
            animationDelay: p.delay,
            animationDuration: p.duration,
          }}
        />
      ))}

      {/* Data stream decorativo */}
      <div className="pointer-events-none absolute right-3 top-6 flex flex-col gap-0.5 font-mono text-[7px]" style={{ color: "rgba(74,222,128,0.3)" }}>
        {DATA_LINES.map((line, i) => (
          <span
            key={line}
            className="animate-data-tick"
            style={{ animationDelay: `${i * 0.3}s` }}
          >
            {line}
          </span>
        ))}
      </div>

      <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-subtext animate-fade-up">
        Toca para analizar
      </p>

      {/* Orbe — toda el área es CTA de scan */}
      <Link
        href="/scan"
        aria-label="Escanear producto"
        className="animate-fade-up relative flex items-center justify-center"
        style={{ width: 260, height: 260, animationDelay: "0.1s" }}
      >
        {/* Pulse rings */}
        <div
          className="orb-ring animate-pulse-ring"
          style={{ width: 182, height: 182, border: "1px solid rgba(74,222,128,0.3)" }}
        />
        <div
          className="orb-ring animate-pulse-ring"
          style={{ width: 182, height: 182, border: "1px solid rgba(74,222,128,0.18)", animationDelay: "0.85s" }}
        />

        {/* Ring orbital exterior (CW) */}
        <div
          className="orb-ring bs-orbital-ring-outer"
          style={{ width: 242, height: 242, border: "1px dashed rgba(74,222,128,0.14)" }}
        >
          <div
            className="absolute"
            style={{
              width: 9,
              height: 9,
              borderRadius: "50%",
              background: "#4ade80",
              boxShadow: "0 0 8px rgba(74,222,128,0.9), 0 0 16px rgba(74,222,128,0.4)",
              top: -4.5,
              left: "50%",
              transform: "translateX(-50%)",
            }}
          />
        </div>

        {/* Ring orbital interior (CCW) */}
        <div
          className="orb-ring bs-orbital-ring-inner"
          style={{ width: 212, height: 212, border: "1px solid rgba(74,222,128,0.07)" }}
        >
          <div
            className="absolute"
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "rgba(74,222,128,0.5)",
              boxShadow: "0 0 5px rgba(74,222,128,0.5)",
              bottom: -3.5,
              right: "18%",
            }}
          />
        </div>

        {/* Core orb con mascota */}
        <div
          className="animate-glow-surge relative z-10 flex items-center justify-center overflow-hidden"
          style={{
            width: 164,
            height: 164,
            borderRadius: "50%",
            background: "radial-gradient(circle at 38% 34%, rgba(74,222,128,0.22) 0%, rgba(74,222,128,0.03) 70%)",
            border: "1.5px solid rgba(74,222,128,0.5)",
          }}
        >
          <Image
            src="/avatars/main.png"
            alt=""
            aria-hidden
            width={126}
            height={126}
            className="animate-avatar-float object-contain"
            style={{ filter: "drop-shadow(0 0 14px rgba(74,222,128,0.6))" }}
            priority
          />
        </div>
      </Link>

      <div className="text-center animate-fade-up" style={{ animationDelay: "0.2s" }}>
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] font-bold text-brand-green">
          Escanear producto
        </p>
        <p className="font-sans text-xs text-subtext mt-0.5">Barcode · Foto · IA</p>
      </div>
    </div>
  );
}
