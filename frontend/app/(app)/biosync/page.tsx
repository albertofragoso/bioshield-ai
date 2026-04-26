"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { toast } from "sonner";
import {
  ArrowLeft,
  ShieldCheck,
  AlertTriangle,
  Upload,
  Trash2,
  X,
  CheckCircle,
} from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { AvatarGlow } from "@/components/AvatarGlow";
import { extractBiomarkers, uploadBiomarkers, getBiomarkerStatus, deleteBiomarkers } from "@/lib/api/biosync";
import { HttpError } from "@/lib/api/client";
import type { Biomarker, BiomarkerExtractionResult, AvatarVariant } from "@/lib/api/types";

/* ── Canonical biomarker display names ────────────────────── */

const BIOMARKER_LABELS: Record<string, string> = {
  ldl: "LDL Colesterol", hdl: "HDL Colesterol", total_cholesterol: "Colesterol Total",
  triglycerides: "Triglicéridos", glucose: "Glucosa en ayuno", hba1c: "HbA1c",
  sodium: "Sodio", potassium: "Potasio", uric_acid: "Ácido úrico", creatinine: "Creatinina",
  alt: "ALT (TGP)", ast: "AST (TGO)", tsh: "TSH", vitamin_d: "Vitamina D",
  iron: "Hierro sérico", ferritin: "Ferritina", hemoglobin: "Hemoglobina",
  hematocrit: "Hematocrito", platelets: "Plaquetas", wbc: "Leucocitos (WBC)", other: "Otro",
};

function classLabel(c: string) {
  if (c === "high") return { text: "Alto", color: "#FB923C", bg: "rgba(251,146,60,.12)", border: "rgba(251,146,60,.3)" };
  if (c === "low")  return { text: "Bajo", color: "#60A5FA", bg: "rgba(96,165,250,.12)",  border: "rgba(96,165,250,.3)" };
  if (c === "normal") return { text: "Normal", color: "#4ADE80", bg: "rgba(74,222,128,.12)", border: "rgba(74,222,128,.3)" };
  return { text: "—", color: "#6B8A6A", bg: "transparent", border: "rgba(74,222,128,.12)" };
}

function aggregateAvatar(biomarkers: Biomarker[]): AvatarVariant {
  const outOfRange = biomarkers.filter((b) => b.classification === "high" || b.classification === "low");
  if (outOfRange.length === 0) return "blue";
  if (outOfRange.length === 1) return "yellow";
  return "orange";
}

function aggregateHeaderCopy(avatar: AvatarVariant): string {
  if (avatar === "blue")   return "Todo se ve bien por ahora.";
  if (avatar === "yellow") return "Encontramos un valor fuera de rango — lo usaremos para personalizar tus scans.";
  return "Encontramos algunos valores fuera de rango — los usaremos para personalizar tus scans.";
}

/* ── Types ─────────────────────────────────────────────────── */

type FlowState = "upload" | "loading" | "review";

/* ── Page ─────────────────────────────────────────────────── */

export default function BiosyncPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [flow, setFlow] = useState<FlowState>("upload");
  const [isDragging, setIsDragging] = useState(false);
  const [extraction, setExtraction] = useState<BiomarkerExtractionResult | null>(null);
  const [editedBiomarkers, setEditedBiomarkers] = useState<Biomarker[]>([]);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const statusQuery = useQuery({
    queryKey: ["biosync-status"],
    queryFn: getBiomarkerStatus,
    retry: (count, err) => !(err instanceof HttpError && err.status === 404),
    staleTime: 5 * 60 * 1000,
  });

  const hasData = statusQuery.data?.has_data === true;
  const expiresAt = statusQuery.data?.expires_at;
  const statusIs404 = statusQuery.isError && statusQuery.error instanceof HttpError && statusQuery.error.status === 404;

  const extractMutation = useMutation({
    mutationFn: extractBiomarkers,
    onMutate: () => setFlow("loading"),
    onSuccess: (data) => {
      setExtraction(data);
      setEditedBiomarkers(data.biomarkers);
      setFlow("review");
    },
    onError: (err) => {
      setFlow("upload");
      if (err instanceof HttpError && err.status === 413) {
        toast.error("PDF demasiado grande", { description: "El límite es 10 MB." });
      } else if (err instanceof HttpError && err.status === 422) {
        toast.error("Archivo inválido", { description: "Solo se aceptan PDFs de resultados de laboratorio." });
      } else {
        toast.error("Error al procesar el PDF", { description: "Intenta de nuevo." });
      }
    },
  });

  const uploadMutation = useMutation({
    mutationFn: uploadBiomarkers,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["biosync-status"] });
      toast.success("Biomarcadores guardados", {
        description: "Tus datos se encriptaron y guardarán por 180 días.",
      });
      setTimeout(() => router.push("/"), 1200);
    },
    onError: () => {
      toast.error("Error al guardar", { description: "Verifica tu red e intenta de nuevo." });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteBiomarkers,
    onSuccess: () => {
      queryClient.resetQueries({ queryKey: ["biosync-status"] });
      setDeleteOpen(false);
      toast.success("Biomarcadores eliminados");
    },
    onError: () => toast.error("No se pudo eliminar. Intenta de nuevo."),
  });

  const handleFile = useCallback((file: File) => {
    const isPdf = file.type === "application/pdf" || file.type === "application/octet-stream";
    const hasPdfExtension = file.name.toLowerCase().endsWith(".pdf");
    if (!isPdf && !hasPdfExtension) {
      toast.error("Solo se aceptan archivos PDF");
      return;
    }
    extractMutation.mutate(file);
  }, [extractMutation]);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function updateValue(idx: number, val: string) {
    const num = parseFloat(val);
    if (isNaN(num)) return;
    setEditedBiomarkers((prev) => prev.map((b, i) => i === idx ? { ...b, value: num } : b));
  }

  function removeRow(idx: number) {
    setEditedBiomarkers((prev) => prev.filter((_, i) => i !== idx));
  }

  function handleConfirm() {
    if (!extraction) return;
    uploadMutation.mutate({
      biomarkers: editedBiomarkers,
      lab_name: extraction.lab_name,
      test_date: extraction.test_date,
    });
  }

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString("es-MX", { day: "2-digit", month: "2-digit", year: "numeric" });
  }

  const avatar = extraction ? aggregateAvatar(editedBiomarkers) : "gray";

  return (
    <div className="relative z-10 min-h-screen px-4 py-6 max-w-[640px] mx-auto">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 font-mono text-[11px] text-subtext hover:text-foreground transition-colors uppercase tracking-[0.08em] mb-6"
      >
        <ArrowLeft size={13} />
        volver
      </Link>

      <h1 className="font-sans font-bold text-xl text-foreground mb-1">Biomarcadores</h1>
      <p className="font-mono text-[11px] text-subtext mb-6 uppercase tracking-[0.08em]">
        BIOSYNC · PERSONAL HEALTH DATA · AES-256
      </p>

      {/* Status banner */}
      {!statusQuery.isLoading && hasData && expiresAt && (
        <div
          className="flex items-start gap-3 px-4 py-3 rounded-input mb-5 font-mono text-[11.5px]"
          style={{ background: "rgba(245,158,11,.08)", border: "1px solid rgba(245,158,11,.3)", color: "#F59E0B" }}
        >
          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          <div className="flex-1">
            Ya tienes biomarcadores activos. Expiran el{" "}
            <span className="font-semibold">{formatDate(expiresAt)}</span>.
            Subir nuevos los reemplaza.
          </div>
          <button
            onClick={() => setDeleteOpen(true)}
            className="shrink-0 flex items-center gap-1 hover:opacity-70 transition-opacity"
            style={{ color: "#F87171" }}
          >
            <Trash2 size={12} />
            Eliminar
          </button>
        </div>
      )}
      {!statusQuery.isLoading && statusIs404 && flow === "upload" && (
        <div
          className="flex items-center gap-3 px-4 py-3 rounded-input mb-5 font-mono text-[11.5px] text-subtext"
          style={{ background: "rgba(74,222,128,.04)", border: "1px solid rgba(74,222,128,.08)" }}
        >
          <CheckCircle size={14} className="shrink-0 text-brand-green" />
          No tienes biomarcadores aún. Sube tu PDF para alertas personalizadas.
        </div>
      )}

      <div className="flex flex-col gap-6">
        <div>
          {/* ── Estado A: Upload ── */}
          {flow === "upload" && (
            <div className="flex flex-col gap-6">
              <div className="flex flex-col items-center justify-center gap-4">
                <AvatarGlow variant="gray" size={140} intensity="soft" />
                <div className="text-center">
                  <p className="font-sans text-sm text-foreground font-medium">Sube tu PDF de laboratorio</p>
                  <p className="font-mono text-[11px] text-subtext mt-0.5">
                    Aceptamos PDFs de cualquier laboratorio.
                  </p>
                </div>
              </div>

              <div
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className="flex flex-col items-center justify-center gap-4 py-12 rounded-card cursor-pointer transition-all"
                style={{
                  border: `2px dashed rgba(74,222,128,${isDragging ? ".5" : ".25"})`,
                  background: isDragging ? "rgba(74,222,128,.05)" : "transparent",
                }}
              >
                <Upload size={28} className="text-brand-green opacity-50" />
                <div className="text-center">
                  <p className="font-sans text-sm text-foreground">Arrastra tu PDF aquí o haz clic</p>
                  <p className="font-mono text-[11px] text-subtext mt-1 uppercase tracking-[0.06em]">
                    Máx. 10 MB · Solo PDF
                  </p>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf,.pdf"
                  className="hidden"
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
                />
              </div>
            </div>
          )}

          {/* ── Estado B: Loading ── */}
          {flow === "loading" && (
            <div className="flex flex-col items-center gap-6 py-10">
              <AvatarGlow variant="blue" size={140} intensity="strong" />
              <div className="text-center">
                <p className="font-sans text-sm text-foreground">Analizando tu PDF con IA…</p>
                <p className="font-mono text-[11px] text-subtext mt-1">
                  Esto toma ~10 segundos. No estamos guardando nada todavía.
                </p>
              </div>
              <div className="w-full max-w-xs h-1 rounded-full overflow-hidden" style={{ background: "rgba(74,222,128,.1)" }}>
                <div className="h-full rounded-full animate-pulse" style={{ background: "#4ADE80", width: "60%" }} />
              </div>
            </div>
          )}

          {/* ── Estado C: Review ── */}
          {flow === "review" && extraction && (
            <div className="flex flex-col gap-5">
              {/* Header con avatar dinámico */}
              <div className="flex flex-col items-center gap-3">
                <AvatarGlow variant={avatar} size={140} intensity="medium" />
                <div className="text-center">
                  <h2 className="font-sans font-semibold text-base text-foreground">
                    Revisa los valores extraídos
                  </h2>
                  <p className="font-mono text-[11px] text-subtext mt-0.5">
                    {aggregateHeaderCopy(avatar)}
                  </p>
                  <div className="flex gap-2 mt-1.5 flex-wrap justify-center">
                    {extraction.lab_name && (
                      <span className="font-mono text-[10px] px-2 py-0.5 rounded-full" style={{ background: "rgba(74,222,128,.1)", color: "#4ADE80" }}>
                        {extraction.lab_name}
                      </span>
                    )}
                    {extraction.test_date && (
                      <span className="font-mono text-[10px] px-2 py-0.5 rounded-full" style={{ background: "rgba(74,222,128,.08)", color: "#6B8A6A" }}>
                        {formatDate(extraction.test_date)}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Tabla editable */}
              <div className="rounded-card overflow-hidden" style={{ border: "1px solid rgba(74,222,128,.12)" }}>
                <table className="w-full text-left">
                  <thead>
                    <tr style={{ background: "rgba(74,222,128,.06)" }}>
                      {["Biomarcador", "Valor", "Rango ref.", "Estado", ""].map((h) => (
                        <th key={h} className="px-3 py-2 font-mono text-[10px] uppercase tracking-[0.08em]" style={{ color: "#6B8A6A" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {editedBiomarkers.map((bm, i) => {
                      const cls = classLabel(bm.classification);
                      const rangeStr = (bm.reference_range_low != null && bm.reference_range_high != null)
                        ? `${bm.reference_range_low}–${bm.reference_range_high}`
                        : "—";
                      return (
                        <tr key={i} style={{ borderTop: "1px solid rgba(74,222,128,.06)" }}>
                          <td className="px-3 py-2.5">
                            <p className="font-sans text-[12px] text-foreground">{BIOMARKER_LABELS[bm.name] ?? bm.name}</p>
                            <p className="font-mono text-[10px] text-subtext">{bm.raw_name}</p>
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="flex items-center gap-1.5">
                              <input
                                type="number"
                                step="any"
                                defaultValue={bm.value}
                                onBlur={(e) => updateValue(i, e.target.value)}
                                className="w-16 px-2 py-1 rounded font-mono text-[12px] text-foreground bg-transparent outline-none"
                                style={{ border: "1px solid rgba(74,222,128,.2)" }}
                              />
                              <span className="font-mono text-[10px] text-subtext">{bm.unit}</span>
                            </div>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className="font-mono text-[10px] text-subtext">{rangeStr}</span>
                            {bm.reference_source !== "none" && (
                              <span
                                className="ml-1 px-1 py-0.5 rounded font-mono text-[9px]"
                                style={{ background: "rgba(74,222,128,.08)", color: "#6B8A6A" }}
                              >
                                {bm.reference_source === "lab" ? "lab" : "canónico"}
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2.5">
                            <span
                              className="px-2 py-0.5 rounded-full font-mono text-[10px]"
                              style={{ background: cls.bg, border: `1px solid ${cls.border}`, color: cls.color }}
                            >
                              {cls.text}
                            </span>
                          </td>
                          <td className="px-2 py-2.5">
                            <button onClick={() => removeRow(i)} className="text-subtext hover:text-foreground transition-colors" aria-label="Eliminar fila">
                              <X size={14} />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {editedBiomarkers.length === 0 && (
                <p className="font-mono text-[11px] text-subtext text-center py-2">
                  No quedan biomarcadores. Sube otro PDF.
                </p>
              )}

              {/* Acciones */}
              <div className="flex flex-col gap-2">
                <button
                  onClick={handleConfirm}
                  disabled={uploadMutation.isPending || editedBiomarkers.length === 0}
                  className="w-full py-3 rounded-button font-mono text-[13px] uppercase tracking-[0.1em] text-brand-green transition-all bs-glow-green hover:bs-glow-green-strong disabled:opacity-40"
                  style={{ background: "rgba(74,222,128,.12)", border: "1px solid rgba(74,222,128,.3)" }}
                >
                  {uploadMutation.isPending ? "Guardando…" : "Confirmar y guardar"}
                </button>
                <button
                  onClick={() => { setFlow("upload"); setExtraction(null); setEditedBiomarkers([]); }}
                  className="w-full py-2 rounded-button font-mono text-[12px] uppercase tracking-[0.08em] text-subtext hover:text-foreground transition-colors"
                  style={{ border: "1px solid rgba(74,222,128,.1)" }}
                >
                  Subir otro PDF
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Privacy card */}
        <PrivacyCard />
      </div>

      {/* Delete modal */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent className="max-w-sm font-sans" style={{ background: "#0A110A", border: "1px solid rgba(248,113,113,.25)" }}>
          <DialogHeader>
            <DialogTitle className="font-sans text-base text-foreground">Eliminar biomarcadores</DialogTitle>
          </DialogHeader>
          <p className="font-mono text-[12px] text-subtext leading-[1.6]">
            Se eliminarán permanentemente todos tus biomarcadores actuales.
            Los análisis futuros no podrán personalizarse hasta que los subas de nuevo.
          </p>
          <DialogFooter className="gap-2 flex-row justify-end">
            <button onClick={() => setDeleteOpen(false)} className="px-4 py-2 rounded-button font-mono text-[12px] text-subtext hover:text-foreground transition-colors">
              Cancelar
            </button>
            <button
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
              className="px-4 py-2 rounded-button font-mono text-[12px] uppercase tracking-[0.08em] disabled:opacity-40 transition-all"
              style={{ background: "rgba(248,113,113,.12)", border: "1px solid rgba(248,113,113,.3)", color: "#F87171" }}
            >
              {deleteMutation.isPending ? "Eliminando…" : "Eliminar"}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function PrivacyCard() {
  return (
    <div className="rounded-card px-5 py-5 flex flex-col gap-4" style={{ background: "rgba(74,222,128,.05)", border: "1px solid rgba(74,222,128,.15)" }}>
      <div className="flex items-center gap-2">
        <ShieldCheck size={16} className="text-brand-green shrink-0" />
        <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-brand-green">Privacidad y seguridad</span>
      </div>
      <ul className="flex flex-col gap-2">
        {[
          "Encriptados con AES-256 antes de guardarse.",
          "Se borran automáticamente después de 180 días.",
          "Nunca se comparten ni se usan para entrenar modelos.",
          "Puedes eliminarlos en cualquier momento.",
        ].map((bullet) => (
          <li key={bullet} className="font-mono text-[11px] leading-[1.5] flex gap-2" style={{ color: "#6B8A6A" }}>
            <span className="text-brand-green shrink-0">·</span>
            {bullet}
          </li>
        ))}
      </ul>
    </div>
  );
}
