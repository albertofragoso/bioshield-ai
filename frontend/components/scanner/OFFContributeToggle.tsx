"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { contributeToOff } from "@/lib/api/scan";
import type { ScanResponse } from "@/lib/api/types";

interface Props {
  scanData: ScanResponse;
}

export function OFFContributeToggle({ scanData }: Props) {
  const [enabled, setEnabled] = useState(false);
  const [succeeded, setSucceeded] = useState(false);

  const mutation = useMutation({
    mutationFn: () =>
      contributeToOff({
        barcode: scanData.product_barcode,
        ingredients: scanData.ingredients.map((i) => i.name),
        consent: true,
      }),
    onSuccess: () => setSucceeded(true),
  });

  const isLoading = mutation.isPending;
  const isError = mutation.isError;

  function handleToggle() {
    if (isLoading) return;
    setEnabled((prev) => !prev);
    mutation.reset();
  }

  function handleSubmit() {
    mutation.mutate();
  }

  function handleRetry() {
    mutation.reset();
    mutation.mutate();
  }

  if (succeeded) {
    return (
      <div
        className="px-4 py-3 rounded-input flex items-center gap-3"
        style={{ background: "rgba(74,222,128,.06)", border: "1px solid rgba(74,222,128,.25)" }}
      >
        <span className="font-mono text-[14px]" style={{ color: "#4ADE80" }}>
          ✓
        </span>
        <div>
          <p className="font-mono text-[11px] text-brand-green uppercase tracking-[0.08em]">
            CONTRIBUCIÓN ENVIADA
          </p>
          <p className="font-sans text-[12px] text-subtext mt-0.5">
            Gracias. Los datos estarán en Open Food Facts pronto.
          </p>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div
        className="px-4 py-3 rounded-input flex items-center justify-between gap-4"
        style={{ background: "rgba(248,113,113,.06)", border: "1px solid rgba(248,113,113,.2)" }}
      >
        <div>
          <p
            className="font-mono text-[11px] uppercase tracking-[0.08em]"
            style={{ color: "#F87171" }}
          >
            ERROR AL ENVIAR
          </p>
          <p className="font-sans text-[12px] text-subtext mt-0.5">
            No se pudo enviar la contribución.
          </p>
        </div>
        <button
          onClick={handleRetry}
          className="shrink-0 px-3 py-1.5 rounded-button font-mono text-[10px] uppercase tracking-[0.08em] transition-opacity hover:opacity-70"
          style={{
            background: "rgba(248,113,113,.1)",
            border: "1px solid rgba(248,113,113,.3)",
            color: "#F87171",
          }}
        >
          REINTENTAR
        </button>
      </div>
    );
  }

  return (
    <div
      className="px-4 py-3 rounded-input flex items-center justify-between gap-4"
      style={{
        background: enabled ? "rgba(74,222,128,.04)" : "rgba(255,255,255,.02)",
        border: `1px solid ${enabled ? "rgba(74,222,128,.2)" : "rgba(255,255,255,.06)"}`,
        transition: "all 0.2s",
      }}
    >
      <div className="flex-1 min-w-0">
        <p
          className="font-mono text-[11px] uppercase tracking-[0.08em]"
          style={{ color: enabled ? "#4ADE80" : "#94a3b8" }}
        >
          CONTRIBUIR A OPEN FOOD FACTS
        </p>

        {isLoading ? (
          <p className="font-sans text-[12px] text-subtext mt-0.5 flex items-center gap-1.5">
            <Spinner />
            Enviando contribución…
          </p>
        ) : enabled ? (
          <>
            <p className="font-sans text-[12px] text-subtext mt-0.5">
              Se compartirá: barcode · ingredientes detectados
            </p>
            <button
              onClick={handleSubmit}
              className="mt-2 px-3 py-1.5 rounded-button font-mono text-[10px] uppercase tracking-[0.08em] text-brand-green transition-all hover:opacity-80"
              style={{
                background: "rgba(74,222,128,.12)",
                border: "1px solid rgba(74,222,128,.35)",
              }}
            >
              ENVIAR →
            </button>
          </>
        ) : (
          <p className="font-sans text-[12px] text-subtext mt-0.5">
            Ayuda a identificar este producto a otros usuarios
          </p>
        )}
      </div>

      {!isLoading && (
        <button
          role="switch"
          aria-checked={enabled}
          aria-label="Contribuir a Open Food Facts"
          onClick={handleToggle}
          className="shrink-0"
          style={{
            width: "40px",
            height: "22px",
            borderRadius: "11px",
            border: `1px solid ${enabled ? "rgba(74,222,128,.5)" : "rgba(255,255,255,.1)"}`,
            background: enabled ? "rgba(74,222,128,.25)" : "rgba(255,255,255,.06)",
            display: "flex",
            alignItems: "center",
            padding: "3px",
            cursor: "pointer",
            transition: "all 0.2s",
          }}
        >
          <span
            style={{
              width: "15px",
              height: "15px",
              borderRadius: "50%",
              background: enabled ? "#4ADE80" : "#334155",
              marginLeft: enabled ? "auto" : "0",
              boxShadow: enabled ? "0 0 6px rgba(74,222,128,.6)" : "none",
              transition: "all 0.2s",
              display: "block",
            }}
          />
        </button>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <svg
      width="11"
      height="11"
      viewBox="0 0 14 14"
      fill="none"
      className="animate-spin shrink-0"
      aria-hidden
    >
      <circle
        cx="7"
        cy="7"
        r="5.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeDasharray="22"
        strokeDashoffset="10"
        strokeLinecap="round"
      />
    </svg>
  );
}
