"use client";

import { useState, useEffect } from "react";

export function RegulatoryBanner() {
  const [dismissed, setDismissed] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const genesis = document.getElementById("genesis");

    if (!genesis) {
      // Not on the marketing page — show banner immediately.
      setVisible(true);
      return;
    }

    // Show banner only AFTER genesis is completely scrolled out of the viewport.
    // While genesis is visible the banner would overlap the scroll hint at the
    // bottom of the genesis section, so it must stay hidden until the user has
    // scrolled past it.
    const checkVisibility = () => {
      const rect = genesis.getBoundingClientRect();
      setVisible(rect.bottom <= 0);
    };

    // Fire immediately to set initial state.
    checkVisibility();

    window.addEventListener("scroll", checkVisibility, { passive: true });
    window.addEventListener("resize", checkVisibility, { passive: true });
    return () => {
      window.removeEventListener("scroll", checkVisibility);
      window.removeEventListener("resize", checkVisibility);
    };
  }, []);

  if (dismissed) return null;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-between gap-4 px-4 py-3 border-t border-border"
      style={{
        background: "var(--surface)",
        // Tailwind v4 quirk: translate-y-full sets CSS `translate` property directly,
        // but translate-y-0 only updates the CSS variable — the property never resets.
        // Inline transform is the reliable cross-version fix.
        transform: visible ? "translateY(0)" : "translateY(100%)",
        transition: "transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)",
      }}
    >
      <p className="font-mono text-[10px] text-subtext leading-tight max-w-2xl">
        <span className="text-brand-amber font-medium">Aviso: </span>
        Herramienta educativa. No sustituye consulta médica. No avalada por COFEPRIS ni FDA.
        Información basada en bases de datos regulatorias públicas.
      </p>
      <button
        onClick={() => setDismissed(true)}
        className="font-mono text-[11px] text-subtext hover:text-foreground shrink-0 transition-colors"
        aria-label="Cerrar aviso regulatorio"
      >
        ✕
      </button>
    </div>
  );
}
