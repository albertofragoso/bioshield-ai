"use client";

import { useState } from "react";

interface DemoDisclaimerModalProps {
  onAccept: () => void;
}

export function DemoDisclaimerModal({ onAccept }: DemoDisclaimerModalProps) {
  const [checked, setChecked] = useState(false);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div
        className="border border-border rounded-card p-6 max-w-md w-full mx-4 shadow-2xl"
        style={{ background: "var(--surface)" }}
      >
        <h3 className="font-sans text-lg font-semibold text-foreground mb-3">
          Antes de ver el demo
        </h3>
        <p className="font-mono text-[12px] text-subtext leading-relaxed mb-4">
          Lo que estás a punto de ver es una simulación con datos reales pre-grabados. BioShield AI
          es una herramienta educativa e informativa.{" "}
          <strong className="text-foreground">
            No diagnostica enfermedades ni reemplaza la consulta médica.
          </strong>
        </p>

        <label className="flex items-start gap-3 cursor-pointer mb-6">
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
            className="mt-0.5 accent-[#4ade80]"
          />
          <span className="font-mono text-[11px] text-subtext">
            Entiendo que esto no es diagnóstico médico y que la información mostrada es educativa.
          </span>
        </label>

        <button
          disabled={!checked}
          onClick={onAccept}
          className="w-full py-2.5 rounded-button font-mono text-[12px] uppercase tracking-[0.08em] text-brand-green transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          style={{
            background: checked ? "rgba(74,222,128,.15)" : "transparent",
            border: "1.5px solid rgba(74,222,128,.5)",
          }}
        >
          Ver demo
        </button>
      </div>
    </div>
  );
}
