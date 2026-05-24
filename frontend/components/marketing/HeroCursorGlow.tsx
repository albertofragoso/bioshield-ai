"use client";

import { useEffect, useRef } from "react";

export function HeroCursorGlow() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onMove = (e: MouseEvent) => {
      el.style.background = `radial-gradient(ellipse 700px 500px at ${e.clientX}px ${e.clientY}px, rgba(13,148,136,0.08) 0%, transparent 70%)`;
    };
    window.addEventListener("mousemove", onMove, { passive: true });
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  return (
    <div
      ref={ref}
      className="pointer-events-none fixed inset-0 z-0 transition-[background] duration-150"
      aria-hidden="true"
    />
  );
}
