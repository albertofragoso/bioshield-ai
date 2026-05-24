"use client";

import Image from "next/image";

interface MascotGuideProps {
  src: string;
  alt: string;
  speech: string;
  size?: "sm" | "md" | "lg";
}

const sizeMap = {
  sm: { px: 72, text: "text-sm" },
  md: { px: 96, text: "text-sm" },
  lg: { px: 120, text: "text-base" },
} as const;

export function MascotGuide({ src, alt, speech, size = "md" }: MascotGuideProps) {
  const { px, text } = sizeMap[size];

  return (
    <>
      <style>{`
        @keyframes mascot-float {
          0%, 100% { transform: translateY(-4px); }
          50%       { transform: translateY(0); }
        }
        @keyframes mascot-glow-pulse {
          0%, 100% { opacity: 0.35; transform: scale(1); }
          50%       { opacity: 0.7;  transform: scale(1.12); }
        }
        @media (prefers-reduced-motion: no-preference) {
          .mascot-float { animation: mascot-float 3s ease-in-out infinite; }
          .mascot-glow  { animation: mascot-glow-pulse 3s ease-in-out infinite; }
        }
      `}</style>

      <div className="flex items-center gap-3">
        {/* Avatar + glow ring */}
        <div className="mascot-float shrink-0 relative" style={{ width: px, height: px }}>
          {/* Breathing glow behind avatar */}
          <div
            className="mascot-glow absolute inset-0 rounded-full pointer-events-none"
            style={{
              background: "radial-gradient(circle, rgba(13,148,136,0.45) 0%, transparent 70%)",
              inset: "-12px",
            }}
            aria-hidden="true"
          />
          <Image
            src={src}
            alt={alt}
            width={px}
            height={px}
            sizes={`${px}px`}
            className="relative z-10 object-contain w-full h-full drop-shadow-[0_0_16px_rgba(13,148,136,0.5)]"
          />
        </div>

        {/* Speech bubble — only when speech is provided */}
        {speech && (
          <div className="relative">
            <span
              className="absolute left-0 top-1/2 -translate-x-full -translate-y-1/2 border-[6px] border-transparent"
              style={{ borderRightColor: "#1a1a2e" }}
              aria-hidden="true"
            />
            <div
              className={`${text} text-white bg-[#111] border border-[#1a1a2e] rounded-lg rounded-tl-none px-3 py-2 leading-snug`}
            >
              {speech}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
