import Image from "next/image";
import type { AvatarVariant } from "@/lib/api/types";

type Intensity = "soft" | "medium" | "strong";

interface AvatarGlowProps {
  variant: AvatarVariant;
  size?: number;
  intensity?: Intensity;
  className?: string;
}

const GLOW_COLOR: Record<AvatarVariant, string> = {
  gray:   "rgba(168,179,167,",
  blue:   "rgba(96,165,250,",
  yellow: "rgba(250,204,21,",
  orange: "rgba(251,146,60,",
  red:    "rgba(248,113,113,",
};

const INTENSITY_ALPHA: Record<Intensity, { idle: string; peak: string }> = {
  soft:   { idle: "0.15)", peak: "0.30)" },
  medium: { idle: "0.25)", peak: "0.50)" },
  strong: { idle: "0.35)", peak: "0.70)" },
};

export function AvatarGlow({ variant, size = 80, intensity = "medium", className = "" }: AvatarGlowProps) {
  const base = GLOW_COLOR[variant];
  const { idle, peak } = INTENSITY_ALPHA[intensity];

  return (
    <Image
      src={`/avatars/${variant}.png`}
      alt=""
      aria-hidden
      width={size}
      height={size}
      className={`animate-pulse-glow object-contain shrink-0 ${className}`}
      style={
        {
          filter: `drop-shadow(0 0 ${Math.round(size * 0.3)}px ${base}${intensity === "soft" ? idle : intensity === "medium" ? idle : peak})`,
        } as React.CSSProperties
      }
    />
  );
}
