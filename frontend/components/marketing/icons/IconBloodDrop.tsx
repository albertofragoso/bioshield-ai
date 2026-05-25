import React from "react";

interface IconBloodDropProps {
  size?: number;
  className?: string;
}

export const IconBloodDrop: React.FC<IconBloodDropProps> = ({ size = 32, className = "" }) => {
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
        <filter id="dropGlow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="1.5" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Blood drop shape */}
      <path
        d="M 16 4 C 16 4 12 10 12 14 C 12 18.4183 13.7909 22 16 22 C 18.2091 22 20 18.4183 20 14 C 20 10 16 4 16 4 Z"
        fill="#F87171"
        filter="url(#dropGlow)"
      />

      {/* Range indicator lines inside drop */}
      {/* Up arrow (↑) - high range */}
      <g transform="translate(16, 10)">
        <path
          d="M 0 2 L 0 -2 M -1.5 0 L 0 -2 L 1.5 0"
          stroke="#FFFFFF"
          strokeWidth="1"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </g>

      {/* Down arrow (↓) - low range */}
      <g transform="translate(16, 16)">
        <path
          d="M 0 -2 L 0 2 M -1.5 0 L 0 2 L 1.5 0"
          stroke="#FFFFFF"
          strokeWidth="1"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </g>

      {/* Equal sign (=) - normal range */}
      <g transform="translate(16, 13)">
        <line
          x1="-2"
          y1="-1"
          x2="2"
          y2="-1"
          stroke="#FFFFFF"
          strokeWidth="1"
          strokeLinecap="round"
        />
        <line x1="-2" y1="1" x2="2" y2="1" stroke="#FFFFFF" strokeWidth="1" strokeLinecap="round" />
      </g>
    </svg>
  );
};

export default IconBloodDrop;
