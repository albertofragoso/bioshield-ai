import React from "react";

interface IconENumberProps {
  size?: number;
  className?: string;
}

export const IconENumber: React.FC<IconENumberProps> = ({ size = 32, className = "" }) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Glow effect */}
      <defs>
        <filter id="enumberGlow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="1.5" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Main circle background */}
      <circle
        cx="14"
        cy="16"
        r="11"
        fill="none"
        stroke="#4ADE80"
        strokeWidth="2"
        filter="url(#enumberGlow)"
      />

      {/* E4 text in circle */}
      <text
        x="14"
        y="19"
        textAnchor="middle"
        fontSize="10"
        fontWeight="600"
        fill="#4ADE80"
        fontFamily="system-ui, -apple-system, sans-serif"
      >
        E4
      </text>

      {/* Amber badge with E-number overlay in top-right */}
      <circle cx="24" cy="8" r="6" fill="#F59E0B" filter="url(#enumberGlow)" />

      {/* Badge text "07" */}
      <text
        x="24"
        y="11"
        textAnchor="middle"
        fontSize="8"
        fontWeight="700"
        fill="#FFFFFF"
        fontFamily="system-ui, -apple-system, sans-serif"
      >
        07
      </text>
    </svg>
  );
};

export default IconENumber;
