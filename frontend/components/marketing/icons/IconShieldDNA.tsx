import React from "react";

interface IconShieldDNAProps {
  size?: number;
  className?: string;
}

export const IconShieldDNA: React.FC<IconShieldDNAProps> = ({ size = 32, className = "" }) => {
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
        <filter id="shieldGlow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="1.5" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Shield background */}
      <path
        d="M 16 3 L 8 7 L 8 15 C 8 22 16 27 16 27 C 16 27 24 22 24 15 L 24 7 L 16 3 Z"
        fill="none"
        stroke="#4ADE80"
        strokeWidth="2"
        filter="url(#shieldGlow)"
      />

      {/* DNA Helix - left strand */}
      <path
        d="M 13 9 Q 12 11 13 13 Q 14 15 15 17 Q 14 19 13 21"
        stroke="#4ADE80"
        strokeWidth="1.5"
        fill="none"
        strokeLinecap="round"
      />

      {/* DNA Helix - right strand */}
      <path
        d="M 19 9 Q 20 11 19 13 Q 18 15 17 17 Q 18 19 19 21"
        stroke="#4ADE80"
        strokeWidth="1.5"
        fill="none"
        strokeLinecap="round"
      />

      {/* DNA crossbars connecting strands */}
      <line x1="13" y1="11" x2="19" y2="11" stroke="#4ADE80" strokeWidth="1" opacity="0.8" />
      <line x1="15" y1="15" x2="17" y2="15" stroke="#4ADE80" strokeWidth="1" opacity="0.8" />
      <line x1="13" y1="19" x2="19" y2="19" stroke="#4ADE80" strokeWidth="1" opacity="0.8" />
    </svg>
  );
};
