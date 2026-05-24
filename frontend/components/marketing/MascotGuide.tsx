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
        @media (prefers-reduced-motion: no-preference) {
          .mascot-float {
            animation: mascot-float 3s ease-in-out infinite;
          }
        }
      `}</style>

      <div className="flex items-center gap-3">
        {/* Avatar */}
        <div
          className="mascot-float shrink-0 rounded-2xl shadow-[0_0_20px_rgba(13,148,136,0.4)] overflow-hidden"
          style={{ width: px, height: px }}
        >
          <Image
            src={src}
            alt={alt}
            width={px}
            height={px}
            sizes={`${px}px`}
            className="rounded-2xl object-cover"
          />
        </div>

        {/* Speech bubble */}
        <div className="relative">
          {/* Left notch/arrow */}
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
      </div>
    </>
  );
}
