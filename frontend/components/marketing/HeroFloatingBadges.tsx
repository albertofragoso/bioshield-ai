"use client";

import React from "react";

interface Badge {
  name: string;
  icon: string;
  color: string;
  bg: string;
  border: string;
  delay: string;
  pos: React.CSSProperties;
}

const BADGES: Badge[] = [
  {
    name: "Tartrazina E102",
    icon: "🚨",
    color: "#f87171",
    bg: "rgba(45,15,15,0.88)",
    border: "#4a1010",
    delay: "0s",
    pos: { top: "-18px", right: "-64px" },
  },
  {
    name: "Carragenano",
    icon: "⚠️",
    color: "#f59e0b",
    bg: "rgba(45,31,0,0.88)",
    border: "#4a3000",
    delay: "1.2s",
    pos: { bottom: "16px", left: "-52px" },
  },
  {
    name: "Vitamina C",
    icon: "✓",
    color: "#0d9488",
    bg: "rgba(13,46,46,0.88)",
    border: "#0d4a3a",
    delay: "2.4s",
    pos: { top: "44%", right: "-72px" },
  },
];

export function HeroFloatingBadges() {
  return (
    <>
      <style>{`
        @keyframes badge-drift {
          0%, 100% { transform: translateY(0px) rotate(-1deg); }
          50%       { transform: translateY(-9px) rotate(1deg); }
        }
        @media (prefers-reduced-motion: reduce) {
          .hero-badge-anim { animation: none !important; }
        }
      `}</style>

      {BADGES.map((b) => (
        <div
          key={b.name}
          className="absolute pointer-events-none z-20"
          style={b.pos}
          aria-hidden="true"
        >
          <div
            className="hero-badge-anim whitespace-nowrap"
            style={{
              animation: `badge-drift 4s ease-in-out infinite`,
              animationDelay: b.delay,
              background: b.bg,
              border: `1px solid ${b.border}`,
              borderRadius: "9999px",
              padding: "3px 10px",
              fontSize: "10px",
              fontFamily: "monospace",
              color: b.color,
              backdropFilter: "blur(10px)",
              letterSpacing: "0.04em",
            }}
          >
            {b.icon} {b.name}
          </div>
        </div>
      ))}
    </>
  );
}
