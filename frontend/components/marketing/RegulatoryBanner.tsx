"use client";

import { useState } from "react";

export function RegulatoryBanner() {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-between gap-4 px-4 py-3 border-t border-border"
      style={{ background: "var(--surface)" }}
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
