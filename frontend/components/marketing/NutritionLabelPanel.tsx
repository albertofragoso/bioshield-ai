"use client";

import { IconBloodDrop } from "@/components/marketing/icons";

/**
 * NutritionLabelPanel — sticky visual panel for the scrollytelling section.
 *
 * 4 absolutely-positioned layers; GSAP controls opacity transitions.
 * Initial state: layer 1 (label-clean) visible, layers 2–4 opacity-0.
 *
 * GSAP target classes:
 *   .label-clean      → beat 1
 *   .label-additives  → beat 2  (.pill-e407, .pill-e621, .pill-e202 inside)
 *   .blood-overlay    → beat 3
 *   .verdict-card     → beat 4
 *
 * Compliance: BloodOverlay contains NO numeric biomarker values.
 */
export function NutritionLabelPanel() {
  return (
    <div
      className="relative w-full"
      style={{ height: "100vh" }}
      role="region"
      aria-label="Visualización de etiqueta nutricional interactiva"
    >
      {/* ─── Centering wrapper ─── */}
      <div className="absolute inset-0 flex items-center justify-center px-4">
        {/* Label card — max-width fits left column on desktop */}
        <div
          className="relative w-full max-w-sm"
          style={{
            height: "580px",
            background: "#080C07",
            border: "1px solid rgba(74,222,128,0.18)",
            borderRadius: "18px",
            boxShadow: "0 0 32px rgba(74,222,128,0.08), 0 0 8px rgba(74,222,128,0.04)",
          }}
        >
          {/* ══════════════════════════════════════════
              LAYER 1 — LabelClean (beat 1)
              "Lo que crees saber"
          ══════════════════════════════════════════ */}
          <div
            className="label-clean absolute inset-0 overflow-hidden rounded-[18px]"
            style={{ opacity: 1 }}
          >
            <LabelClean />
          </div>

          {/* ══════════════════════════════════════════
              LAYER 2 — LabelWithAdditives (beat 2)
              "Lo que hay realmente"
          ══════════════════════════════════════════ */}
          <div
            className="label-additives absolute inset-0 overflow-hidden rounded-[18px]"
            style={{ opacity: 0 }}
            aria-hidden="true"
          >
            <LabelWithAdditives />
          </div>

          {/* ══════════════════════════════════════════
              LAYER 3 — BloodOverlay (beat 3)
              "Lo que significa para ti"
              NOTE: NO numeric values — only range qualifiers
          ══════════════════════════════════════════ */}
          <div
            className="blood-overlay absolute inset-0 overflow-hidden rounded-[18px]"
            style={{ opacity: 0 }}
            aria-hidden="true"
          >
            <BloodOverlay />
          </div>

          {/* ══════════════════════════════════════════
              LAYER 4 — VerdictCard (beat 4)
              "La brecha cerrada"
          ══════════════════════════════════════════ */}
          <div
            className="verdict-card absolute inset-0 overflow-hidden rounded-[18px]"
            style={{ opacity: 0 }}
            aria-hidden="true"
          >
            <VerdictCard />
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
   Internal layer components
───────────────────────────────────────────────────────── */

function LabelClean() {
  return (
    <div className="w-full h-full flex flex-col bg-[#080C07] p-5">
      {/* Header */}
      <div className="border-b-4 border-[#DCF0DC] pb-1 mb-1">
        <p className="font-mono text-[10px] text-[#6B8A6A] tracking-widest uppercase">
          Información Nutrimental · FDA/COFEPRIS
        </p>
        <p className="font-sans text-base font-extrabold text-[#DCF0DC] leading-tight mt-0.5">
          Yogurt Natural
        </p>
        <p className="font-mono text-[10px] text-[#6B8A6A]">Danone · SKU 7501055300072</p>
      </div>

      {/* Serving size */}
      <div className="border-b border-[rgba(74,222,128,0.18)] py-1.5">
        <p className="font-sans text-[11px] text-[#DCF0DC]">
          Tamaño de porción: <span className="font-bold">150 g</span>
        </p>
      </div>

      {/* Calories row */}
      <div className="border-b-4 border-[#DCF0DC] py-1.5 flex items-baseline justify-between">
        <span className="font-sans text-sm font-bold text-[#DCF0DC]">Calorías</span>
        <span className="font-sans text-3xl font-extrabold text-[#DCF0DC]">90</span>
      </div>

      {/* Nutrient rows */}
      <div className="flex-1 py-1 space-y-1">
        <NutrientRow label="Grasa Total" value="3g" highlight="green" />
        <NutrientRow label="  Grasa Saturada" value="1.5g" />
        <NutrientRow label="  Grasa Trans" value="0g" />
        <NutrientRow label="Colesterol" value="10mg" />
        <NutrientRow label="Sodio" value="75mg" />
        <NutrientRow label="Carbohidratos" value="12g" />
        <NutrientRow label="  Fibra" value="0g" />
        <NutrientRow label="Proteína" value="5g" highlight="green" />
      </div>

      {/* Highlighted claims */}
      <div className="border-t border-[rgba(74,222,128,0.18)] pt-2 space-y-1">
        <Claim text="Proteína 5g" check />
        <Claim text="Grasa Total 3g" check />
        <Claim text="Sin Azúcar Añadida" check />
      </div>

      {/* Ingredients (partial) */}
      <div className="border-t border-[rgba(74,222,128,0.18)] pt-2">
        <p className="font-mono text-[9px] text-[#6B8A6A] leading-relaxed">
          <span className="text-[#DCF0DC] font-semibold">Ingredientes:</span> Leche entera
          pasteurizada, cultivos lácticos activos (S. thermophilus, L. bulgaricus)...
        </p>
      </div>
    </div>
  );
}

function LabelWithAdditives() {
  return (
    <div className="w-full h-full flex flex-col bg-[#080C07] p-5">
      {/* Header — same as clean */}
      <div className="border-b-4 border-[#DCF0DC] pb-1 mb-1">
        <p className="font-mono text-[10px] text-[#6B8A6A] tracking-widest uppercase">
          Información Nutrimental · FDA/COFEPRIS
        </p>
        <p className="font-sans text-base font-extrabold text-[#DCF0DC] leading-tight mt-0.5">
          Yogurt Natural
        </p>
        <p className="font-mono text-[10px] text-[#6B8A6A]">Danone · SKU 7501055300072</p>
      </div>

      {/* Nutrient summary — compressed */}
      <div className="border-b border-[rgba(74,222,128,0.18)] py-1.5 flex gap-4">
        <span className="font-mono text-[10px] text-[#6B8A6A]">
          Cal <span className="text-[#DCF0DC]">90</span>
        </span>
        <span className="font-mono text-[10px] text-[#6B8A6A]">
          Prot <span className="text-[#DCF0DC]">5g</span>
        </span>
        <span className="font-mono text-[10px] text-[#6B8A6A]">
          Gras <span className="text-[#DCF0DC]">3g</span>
        </span>
      </div>

      {/* Ingredients zoomed — main focus */}
      <div className="flex-1 py-2">
        <p className="font-mono text-[10px] text-[#DCF0DC] font-semibold mb-2 uppercase tracking-wide">
          Ingredientes
        </p>
        <p className="font-mono text-[10px] text-[#6B8A6A] leading-relaxed">
          Leche entera pasteurizada, cultivos lácticos activos,{" "}
          <span className="text-[#F59E0B] font-semibold bg-[#F59E0B]/10 px-0.5 rounded">
            carragenina
          </span>
          , azúcar, almidón modificado,{" "}
          <span className="text-[#F59E0B] font-semibold bg-[#F59E0B]/10 px-0.5 rounded">
            glutamato monosódico
          </span>
          , saborizante artificial,{" "}
          <span className="text-[#F59E0B] font-semibold bg-[#F59E0B]/10 px-0.5 rounded">
            sorbato de potasio
          </span>
          .
        </p>

        {/* Additive detail cards */}
        <div className="mt-3 space-y-2">
          <AdditiveRow
            code="E407"
            name="Carragenina"
            note="Espesante · uso controversial"
            pillClass="pill-e407"
          />
          <AdditiveRow
            code="E621"
            name="Glutamato Monosódico"
            note="Potenciador de sabor"
            pillClass="pill-e621"
          />
          <AdditiveRow
            code="E202"
            name="Sorbato de Potasio"
            note="Conservador antimicrobiano"
            pillClass="pill-e202"
          />
        </div>
      </div>

      {/* E-number floating pills */}
      <div className="border-t border-[rgba(74,222,128,0.18)] pt-2 flex gap-2 flex-wrap">
        <EPill code="E407" pillClass="pill-e407" />
        <EPill code="E621" pillClass="pill-e621" />
        <EPill code="E202" pillClass="pill-e202" />
      </div>
    </div>
  );
}

function BloodOverlay() {
  return (
    <div className="w-full h-full relative">
      {/* Clean label at 40% opacity behind */}
      <div className="absolute inset-0 opacity-40">
        <LabelClean />
      </div>

      {/* Red overlay panel */}
      <div className="absolute inset-0 flex flex-col p-5">
        {/* Header */}
        <div className="flex items-center gap-2 mb-4">
          <IconBloodDrop size={28} className="flex-shrink-0" />
          <div>
            <p className="font-sans text-sm font-bold text-[#F87171]">Impacto en tu perfil</p>
            <p className="font-mono text-[9px] text-[#6B8A6A]">Análisis de biomarcadores</p>
          </div>
        </div>

        {/* Range indicators — NO numeric values */}
        <div className="space-y-3 flex-1">
          <RangeIndicatorRow marker="Inflamación" qualifier="↑ elevado" level="high" />
          <RangeIndicatorRow marker="Triglicéridos" qualifier="↑ elevado" level="high" />
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* WATERMARK — always visible, not GSAP-controlled */}
        <div
          className="absolute bottom-4 left-0 right-0 flex justify-center"
          aria-label="Aviso legal"
        >
          <p className="font-mono text-[9px] text-[#6B8A6A] text-center px-4 leading-relaxed">
            Ejemplo ilustrativo · Datos reales solo con tu perfil activo
          </p>
        </div>
      </div>
    </div>
  );
}

function VerdictCard() {
  return (
    <div className="w-full h-full flex flex-col bg-[#080C07] p-5">
      {/* BioShield wordmark */}
      <div className="flex items-center gap-1.5 mb-6">
        <div
          className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
          style={{
            background: "rgba(74,222,128,0.15)",
            border: "1px solid rgba(74,222,128,0.4)",
          }}
        >
          <span className="text-[8px] text-[#4ADE80] font-bold">B</span>
        </div>
        <span className="font-mono text-[11px] font-semibold tracking-widest text-[#4ADE80] uppercase">
          BioShield
        </span>
      </div>

      {/* Semaphore + verdict */}
      <div className="flex-1 flex flex-col items-center justify-center gap-4">
        {/* Red semaphore circle */}
        <div
          className="w-16 h-16 rounded-full flex items-center justify-center"
          style={{
            background: "rgba(248,113,113,0.15)",
            border: "2px solid #F87171",
            boxShadow: "0 0 24px rgba(248,113,113,0.3)",
          }}
          role="img"
          aria-label="No recomendado"
        >
          <span className="font-sans font-extrabold text-2xl" style={{ color: "#F87171" }}>
            !
          </span>
        </div>

        {/* Verdict text */}
        <div className="text-center">
          <p className="font-sans text-lg font-bold text-[#DCF0DC] mb-1">No recomendado</p>
          <p className="font-sans text-sm text-[#6B8A6A]">para tu perfil</p>
        </div>

        {/* CTA */}
        <button
          className="font-sans text-sm font-semibold text-[#4ADE80] flex items-center gap-1 hover:gap-2 transition-all"
          tabIndex={-1}
          aria-hidden="true"
        >
          Ver alternativa
          <span aria-hidden="true">→</span>
        </button>
      </div>

      {/* Footer divider */}
      <div className="border-t border-[rgba(74,222,128,0.18)] pt-3">
        <p className="font-mono text-[9px] text-[#6B8A6A] text-center">
          Análisis generado por BioShield AI
        </p>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
   Micro-components
───────────────────────────────────────────────────────── */

interface NutrientRowProps {
  label: string;
  value: string;
  highlight?: "green";
}

function NutrientRow({ label, value, highlight }: NutrientRowProps) {
  const isGreen = highlight === "green";
  return (
    <div className="flex items-center justify-between border-b border-[rgba(74,222,128,0.08)] py-0.5">
      <span
        className={`font-mono text-[10px] ${isGreen ? "text-[#4ADE80] font-semibold" : "text-[#DCF0DC]"}`}
      >
        {label}
      </span>
      <span
        className={`font-mono text-[10px] font-bold ${isGreen ? "text-[#4ADE80]" : "text-[#DCF0DC]"}`}
      >
        {value}
      </span>
    </div>
  );
}

interface ClaimProps {
  text: string;
  check?: boolean;
}

function Claim({ text, check }: ClaimProps) {
  return (
    <div className="flex items-center gap-1.5">
      {check && <span className="text-[#4ADE80] text-[10px] font-bold">✓</span>}
      <span className="font-mono text-[10px] text-[#4ADE80]">{text}</span>
    </div>
  );
}

interface AdditiveRowProps {
  code: string;
  name: string;
  note: string;
  pillClass: string;
}

function AdditiveRow({ code, name, note, pillClass }: AdditiveRowProps) {
  return (
    <div className="flex items-start gap-2 p-2 rounded-lg bg-[#F59E0B]/5 border border-[#F59E0B]/20">
      <span
        className={`${pillClass} font-mono text-[10px] font-bold text-[#F59E0B] bg-[#F59E0B]/15 px-1.5 py-0.5 rounded flex-shrink-0`}
      >
        {code}
      </span>
      <div className="min-w-0">
        <p className="font-sans text-[11px] font-semibold text-[#DCF0DC] leading-tight">{name}</p>
        <p className="font-mono text-[9px] text-[#6B8A6A]">{note}</p>
      </div>
    </div>
  );
}

interface EPillProps {
  code: string;
  pillClass: string;
}

function EPill({ code, pillClass }: EPillProps) {
  return (
    <span
      className={`${pillClass} font-mono text-[11px] font-bold text-[#F59E0B] bg-[#F59E0B]/15 border border-[#F59E0B]/40 px-2 py-1 rounded-full`}
    >
      {code}
    </span>
  );
}

interface RangeIndicatorRowProps {
  marker: string;
  qualifier: string;
  level: "high" | "normal" | "low";
}

function RangeIndicatorRow({ marker, qualifier, level }: RangeIndicatorRowProps) {
  const colorMap: Record<string, string> = {
    high: "#F87171",
    normal: "#4ADE80",
    low: "#60A5FA",
  };
  const bgMap: Record<string, string> = {
    high: "rgba(248,113,113,0.08)",
    normal: "rgba(74,222,128,0.08)",
    low: "rgba(96,165,250,0.08)",
  };
  const color = colorMap[level];
  const bg = bgMap[level];

  return (
    <div
      className="flex items-center justify-between rounded-lg px-3 py-2"
      style={{ background: bg, border: `1px solid ${color}30` }}
    >
      <span className="font-mono text-[11px] text-[#DCF0DC]">{marker}</span>
      <span className="font-mono text-[11px] font-bold" style={{ color }}>
        {qualifier}
      </span>
    </div>
  );
}
