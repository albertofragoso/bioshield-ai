import React from "react";

interface IconLabelProps {
  size?: number;
  className?: string;
}

export const IconLabel: React.FC<IconLabelProps> = ({ size = 32, className = "" }) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      {/* Glow effect */}
      <defs>
        <filter id="labelGlow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="1.5" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Barcode with variable stroke widths */}
      <g filter="url(#labelGlow)">
        {/* Thin line */}
        <line
          x1="6"
          y1="8"
          x2="6"
          y2="24"
          stroke="#4ADE80"
          strokeWidth="1.5"
          strokeLinecap="round"
        />

        {/* Medium line */}
        <line
          x1="10"
          y1="8"
          x2="10"
          y2="24"
          stroke="#4ADE80"
          strokeWidth="2.5"
          strokeLinecap="round"
        />

        {/* Thick line */}
        <line
          x1="14"
          y1="8"
          x2="14"
          y2="24"
          stroke="#4ADE80"
          strokeWidth="3.5"
          strokeLinecap="round"
        />

        {/* Medium line */}
        <line
          x1="18"
          y1="8"
          x2="18"
          y2="24"
          stroke="#4ADE80"
          strokeWidth="2.5"
          strokeLinecap="round"
        />

        {/* Thin line */}
        <line
          x1="22"
          y1="8"
          x2="22"
          y2="24"
          stroke="#4ADE80"
          strokeWidth="1.5"
          strokeLinecap="round"
        />

        {/* Very thick line */}
        <line
          x1="26"
          y1="8"
          x2="26"
          y2="24"
          stroke="#4ADE80"
          strokeWidth="4"
          strokeLinecap="round"
        />
      </g>

      {/* Bottom baseline */}
      <line x1="4" y1="27" x2="28" y2="27" stroke="#4ADE80" strokeWidth="1" strokeOpacity="0.5" />
    </svg>
  );
};
