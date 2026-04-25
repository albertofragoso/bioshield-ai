import {
  HelpCircle,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  ShieldAlert,
} from "lucide-react";
import type { SemaphoreColor } from "@/lib/api/types";

const CONFIG: Record<SemaphoreColor, { color: string; Icon: React.ElementType; label: string }> = {
  GRAY:   { color: "#A8B3A7", Icon: HelpCircle,    label: "Sin datos suficientes" },
  BLUE:   { color: "#60A5FA", Icon: CheckCircle,   label: "Seguro"               },
  YELLOW: { color: "#FACC15", Icon: AlertCircle,   label: "Precaución"           },
  ORANGE: { color: "#FB923C", Icon: AlertTriangle, label: "Riesgo personal"      },
  RED:    { color: "#F87171", Icon: ShieldAlert,   label: "Prohibido"            },
};

interface Props {
  color: SemaphoreColor;
  size?: number;
  showLabel?: boolean;
  className?: string;
}

export function SemaphoreBadge({ color, size = 40, showLabel = false, className = "" }: Props) {
  const { color: hex, Icon, label } = CONFIG[color];
  const iconSize = Math.round(size * 0.45);

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div
        className="shrink-0 flex items-center justify-center rounded-full"
        style={{
          width: size,
          height: size,
          background: `rgba(${hexToRgb(hex)}, .20)`,
        }}
        aria-label={label}
      >
        <span style={{ color: hex }}>
          <Icon size={iconSize} />
        </span>
      </div>
      {showLabel && (
        <span className="font-mono text-[11px] uppercase tracking-[0.08em]" style={{ color: hex }}>
          {label}
        </span>
      )}
    </div>
  );
}

function hexToRgb(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `${r},${g},${b}`;
}
