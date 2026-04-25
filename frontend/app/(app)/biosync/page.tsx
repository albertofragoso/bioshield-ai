"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { toast } from "sonner";
import {
  ArrowLeft,
  ShieldCheck,
  Info,
  AlertTriangle,
  Plus,
  X,
  Upload,
  Trash2,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { uploadBiomarkers, getBiomarkerStatus, deleteBiomarkers } from "@/lib/api/biosync";
import { HttpError } from "@/lib/api/client";

/* ── Biomarker fields config ──────────────────────────────── */

const KNOWN_FIELDS: Array<{ key: string; label: string; unit: string; hint: string }> = [
  { key: "ldl",           label: "LDL",           unit: "mg/dL",  hint: "Normal: < 100 mg/dL" },
  { key: "hdl",           label: "HDL",           unit: "mg/dL",  hint: "Normal: > 40 mg/dL" },
  { key: "glucose",       label: "Glucosa",       unit: "mg/dL",  hint: "Normal: 70–99 mg/dL" },
  { key: "triglycerides", label: "Triglicéridos", unit: "mg/dL",  hint: "Normal: < 150 mg/dL" },
  { key: "sodium",        label: "Sodio",         unit: "mg/día", hint: "Referencial: < 2300 mg/día" },
  { key: "uric_acid",     label: "Ácido úrico",   unit: "mg/dL",  hint: "Normal: < 7 mg/dL" },
];

/* ── Range warning ────────────────────────────────────────── */

function isOutOfRange(key: string, val: number): boolean {
  if (key === "ldl"           && val >= 100)  return true;
  if (key === "hdl"           && val <= 40)   return true;
  if (key === "glucose"       && (val < 70 || val > 99)) return true;
  if (key === "triglycerides" && val >= 150)  return true;
  if (key === "sodium"        && val >= 2300) return true;
  if (key === "uric_acid"     && val >= 7)    return true;
  return false;
}

/* ── CSV parsing ──────────────────────────────────────────── */

interface ParsedCSV {
  headers: string[];
  rows: string[][];
}

function parseCSV(text: string): ParsedCSV {
  const lines = text.trim().split(/\r?\n/).filter(Boolean);
  if (lines.length === 0) return { headers: [], rows: [] };
  const headers = lines[0].split(",").map((h) => h.trim());
  const rows = lines.slice(1).map((line) => line.split(",").map((c) => c.trim()));
  return { headers, rows };
}

function csvToData(parsed: ParsedCSV): Record<string, number> {
  const result: Record<string, number> = {};
  parsed.rows.forEach((row) => {
    parsed.headers.forEach((header, i) => {
      const val = parseFloat(row[i] ?? "");
      if (!isNaN(val)) result[header] = val;
    });
  });
  return result;
}

/* ── Page ─────────────────────────────────────────────────── */

export default function BiosyncPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  // Estado del tab activo
  const [activeTab, setActiveTab] = useState<"manual" | "csv">("manual");

  // Campos manuales conocidos
  const [manualValues, setManualValues] = useState<Record<string, string>>({});
  // Campos extra (key-value genérico)
  const [extraFields, setExtraFields] = useState<Array<{ key: string; value: string }>>([]);

  // CSV
  const [csvParsed, setCsvParsed] = useState<ParsedCSV | null>(null);
  const [csvFileName, setCsvFileName] = useState("");
  const [csvDragging, setCsvDragging] = useState(false);
  const csvInputRef = useRef<HTMLInputElement>(null);

  // Modal de confirmación de borrado
  const [deleteOpen, setDeleteOpen] = useState(false);

  // Estado del submit
  const [uploadProgress, setUploadProgress] = useState(0);

  /* ── Queries ── */

  const statusQuery = useQuery({
    queryKey: ["biosync-status"],
    queryFn: getBiomarkerStatus,
    retry: (count, err) => !(err instanceof HttpError && err.status === 404),
    staleTime: 5 * 60 * 1000,
  });

  const hasData = statusQuery.data?.has_data === true;
  const expiresAt = statusQuery.data?.expires_at;
  const statusIs404 = statusQuery.isError && statusQuery.error instanceof HttpError && statusQuery.error.status === 404;

  /* ── Mutations ── */

  const uploadMutation = useMutation({
    mutationFn: uploadBiomarkers,
    onMutate: () => { setUploadProgress(30); },
    onSuccess: () => {
      setUploadProgress(100);
      queryClient.invalidateQueries({ queryKey: ["biosync-status"] });
      toast.success("Biomarcadores guardados", {
        description: "Tus datos se encriptaron y guardarán por 180 días.",
        icon: (
          <Image
            src="/avatars/success.png"
            alt=""
            width={28}
            height={28}
            className="object-contain"
          />
        ),
      });
      setTimeout(() => router.push("/"), 1200);
    },
    onError: (err) => {
      setUploadProgress(0);
      if (err instanceof HttpError && err.status === 422) {
        toast.error("Datos inválidos", { description: "Verifica que los valores sean números correctos." });
      } else {
        toast.error("Error de conexión", { description: "Verifica tu red e intenta de nuevo." });
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteBiomarkers,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["biosync-status"] });
      setDeleteOpen(false);
      toast.success("Biomarcadores eliminados");
    },
    onError: () => {
      toast.error("No se pudo eliminar. Intenta de nuevo.");
    },
  });

  /* ── Submit manual ── */

  function handleManualSubmit(e: React.FormEvent) {
    e.preventDefault();
    const data: Record<string, number> = {};
    KNOWN_FIELDS.forEach(({ key }) => {
      const v = parseFloat(manualValues[key] ?? "");
      if (!isNaN(v)) data[key] = v;
    });
    extraFields.forEach(({ key, value }) => {
      const k = key.trim().toLowerCase().replace(/\s+/g, "_");
      const v = parseFloat(value);
      if (k && !isNaN(v)) data[k] = v;
    });
    if (Object.keys(data).length === 0) return;
    uploadMutation.mutate({ data });
  }

  /* ── Submit CSV ── */

  function handleCSVSubmit() {
    if (!csvParsed) return;
    const data = csvToData(csvParsed);
    if (Object.keys(data).length === 0) return;
    uploadMutation.mutate({ data });
  }

  /* ── CSV drop/select ── */

  const handleCSVFile = useCallback((file: File) => {
    if (!file.name.endsWith(".csv")) {
      toast.error("Solo se aceptan archivos .csv");
      return;
    }
    setCsvFileName(file.name);
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      setCsvParsed(parseCSV(text));
    };
    reader.readAsText(file);
  }, []);

  function handleCSVDrop(e: React.DragEvent) {
    e.preventDefault();
    setCsvDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleCSVFile(file);
  }

  /* ── Extra fields ── */

  function addExtraField() {
    setExtraFields((prev) => [...prev, { key: "", value: "" }]);
  }

  function updateExtra(i: number, field: "key" | "value", val: string) {
    setExtraFields((prev) => prev.map((f, idx) => idx === i ? { ...f, [field]: val } : f));
  }

  function removeExtra(i: number) {
    setExtraFields((prev) => prev.filter((_, idx) => idx !== i));
  }

  /* ── Format date ── */

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString("es-MX", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  }

  /* ── Empty state ── */

  if (!statusQuery.isLoading && statusIs404 && Object.keys(manualValues).length === 0 && !csvParsed) {
    // Show empty state only once, before user starts entering data
  }

  const isUploading = uploadMutation.isPending;

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

      {/* ── Status banner ── */}
      {statusQuery.isLoading ? null : hasData && expiresAt ? (
        <div
          className="flex items-start gap-3 px-4 py-3 rounded-input mb-5 font-mono text-[11.5px]"
          style={{
            background: "rgba(245,158,11,.08)",
            border: "1px solid rgba(245,158,11,.3)",
            color: "#F59E0B",
          }}
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
      ) : statusIs404 ? (
        <div
          className="flex items-center gap-3 px-4 py-3 rounded-input mb-5 font-mono text-[11.5px] text-subtext"
          style={{
            background: "rgba(74,222,128,.04)",
            border: "1px solid rgba(74,222,128,.08)",
          }}
        >
          <Info size={14} className="shrink-0 text-brand-green" />
          No tienes biomarcadores aún. Agrégalos para recibir alertas personalizadas.
        </div>
      ) : null}

      {/* ── Main layout ── */}
      <div className="lg:grid lg:grid-cols-[1fr_280px] lg:gap-8 lg:items-start">
        {/* ── Left: form ── */}
        <div>
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as "manual" | "csv")}>
            <TabsList
              className="w-full mb-6"
              style={{
                background: "rgba(74,222,128,.06)",
                border: "1px solid rgba(74,222,128,.1)",
              }}
            >
              <TabsTrigger
                value="manual"
                className="flex-1 font-mono text-[12px] uppercase tracking-[0.06em] data-[state=active]:text-brand-green"
              >
                Manual
              </TabsTrigger>
              <TabsTrigger
                value="csv"
                className="flex-1 font-mono text-[12px] uppercase tracking-[0.06em] data-[state=active]:text-brand-green"
              >
                CSV
              </TabsTrigger>
            </TabsList>

            {/* ── Tab: Manual ── */}
            <TabsContent value="manual">
              <form onSubmit={handleManualSubmit} className="flex flex-col gap-6">
                <div className="flex flex-col gap-4">
                  {KNOWN_FIELDS.map(({ key, label, unit, hint }) => (
                    <BiomarkerField
                      key={key}
                      fieldKey={key}
                      label={label}
                      unit={unit}
                      hint={hint}
                      value={manualValues[key] ?? ""}
                      onChange={(v) => setManualValues((prev) => ({ ...prev, [key]: v }))}
                      disabled={isUploading}
                    />
                  ))}

                  {/* Extra key-value fields */}
                  {extraFields.map((field, i) => (
                    <div key={i} className="flex gap-2 items-start">
                      <div className="flex-1">
                        <input
                          type="text"
                          placeholder="nombre biomarcador"
                          value={field.key}
                          onChange={(e) => updateExtra(i, "key", e.target.value)}
                          disabled={isUploading}
                          className="w-full px-3 py-2.5 rounded-input font-mono text-[12px] text-foreground placeholder:text-subtext bg-transparent outline-none"
                          style={{ border: "1px solid rgba(74,222,128,.15)" }}
                        />
                      </div>
                      <div className="w-24">
                        <input
                          type="number"
                          placeholder="valor"
                          value={field.value}
                          onChange={(e) => updateExtra(i, "value", e.target.value)}
                          disabled={isUploading}
                          className="w-full px-3 py-2.5 rounded-input font-mono text-[12px] text-foreground placeholder:text-subtext bg-transparent outline-none"
                          style={{ border: "1px solid rgba(74,222,128,.15)" }}
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => removeExtra(i)}
                        className="mt-2.5 text-subtext hover:text-foreground transition-colors"
                        aria-label="Eliminar campo"
                      >
                        <X size={16} />
                      </button>
                    </div>
                  ))}

                  <button
                    type="button"
                    onClick={addExtraField}
                    disabled={isUploading}
                    className="self-start flex items-center gap-1.5 font-mono text-[11px] text-brand-green hover:opacity-70 transition-opacity uppercase tracking-[0.08em]"
                  >
                    <Plus size={13} />
                    Agregar otro biomarcador
                  </button>
                </div>

                {isUploading && (
                  <div className="flex flex-col gap-2">
                    <Progress value={uploadProgress} className="h-1" />
                    <p className="font-mono text-[11px] text-subtext uppercase tracking-[0.08em]">
                      Encriptando y subiendo…
                    </p>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isUploading}
                  className="w-full py-3 rounded-button font-mono text-[13px] uppercase tracking-[0.1em] text-brand-green transition-all bs-glow-green hover:bs-glow-green-strong disabled:opacity-40"
                  style={{
                    background: "rgba(74,222,128,.12)",
                    border: "1px solid rgba(74,222,128,.3)",
                  }}
                >
                  {isUploading ? "Guardando…" : "Guardar biomarcadores"}
                </button>
              </form>
            </TabsContent>

            {/* ── Tab: CSV ── */}
            <TabsContent value="csv">
              <div className="flex flex-col gap-5">
                {/* Dropzone */}
                <div
                  onDragOver={(e) => { e.preventDefault(); setCsvDragging(true); }}
                  onDragLeave={() => setCsvDragging(false)}
                  onDrop={handleCSVDrop}
                  onClick={() => csvInputRef.current?.click()}
                  className="flex flex-col items-center justify-center gap-3 py-10 rounded-card cursor-pointer transition-all"
                  style={{
                    border: `2px dashed rgba(74,222,128,${csvDragging ? ".5" : ".3"})`,
                    background: csvDragging ? "rgba(74,222,128,.05)" : "transparent",
                  }}
                >
                  <Upload size={24} className="text-brand-green opacity-60" />
                  <div className="text-center">
                    <p className="font-sans text-sm text-foreground">
                      {csvFileName ? csvFileName : "Arrastra tu .csv o haz clic"}
                    </p>
                    <p className="font-mono text-[11px] text-subtext mt-1 uppercase tracking-[0.08em]">
                      headers en fila 1 · valores numéricos
                    </p>
                  </div>
                  <input
                    ref={csvInputRef}
                    type="file"
                    accept=".csv"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleCSVFile(file);
                    }}
                  />
                </div>

                {/* CSV preview */}
                {csvParsed && csvParsed.headers.length > 0 && (
                  <CSVPreviewTable parsed={csvParsed} />
                )}

                {isUploading && (
                  <div className="flex flex-col gap-2">
                    <Progress value={uploadProgress} className="h-1" />
                    <p className="font-mono text-[11px] text-subtext uppercase tracking-[0.08em]">
                      Encriptando y subiendo…
                    </p>
                  </div>
                )}

                <button
                  type="button"
                  onClick={handleCSVSubmit}
                  disabled={!csvParsed || isUploading}
                  className="w-full py-3 rounded-button font-mono text-[13px] uppercase tracking-[0.1em] text-brand-green transition-all bs-glow-green hover:bs-glow-green-strong disabled:opacity-40"
                  style={{
                    background: "rgba(74,222,128,.12)",
                    border: "1px solid rgba(74,222,128,.3)",
                  }}
                >
                  {isUploading ? "Procesando…" : "Procesar y subir"}
                </button>
              </div>
            </TabsContent>
          </Tabs>
        </div>

        {/* ── Right: Privacy card ── */}
        <div className="mt-6 lg:mt-0 lg:sticky lg:top-[78px]">
          <PrivacyCard />
        </div>
      </div>

      {/* ── Delete confirm modal ── */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent
          className="max-w-sm font-sans"
          style={{
            background: "#0A110A",
            border: "1px solid rgba(248,113,113,.25)",
          }}
        >
          <DialogHeader>
            <DialogTitle className="font-sans text-base text-foreground">
              Eliminar biomarcadores
            </DialogTitle>
          </DialogHeader>
          <p className="font-mono text-[12px] text-subtext leading-[1.6]">
            Se eliminarán permanentemente todos tus biomarcadores actuales.
            Los análisis futuros no podrán personalizarse hasta que los subas de nuevo.
          </p>
          <DialogFooter className="gap-2 flex-row justify-end">
            <button
              onClick={() => setDeleteOpen(false)}
              className="px-4 py-2 rounded-button font-mono text-[12px] text-subtext hover:text-foreground transition-colors"
            >
              Cancelar
            </button>
            <button
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
              className="px-4 py-2 rounded-button font-mono text-[12px] uppercase tracking-[0.08em] disabled:opacity-40 transition-all"
              style={{
                background: "rgba(248,113,113,.12)",
                border: "1px solid rgba(248,113,113,.3)",
                color: "#F87171",
              }}
            >
              {deleteMutation.isPending ? "Eliminando…" : "Eliminar"}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ── Sub-components ───────────────────────────────────────── */

function BiomarkerField({
  fieldKey,
  label,
  unit,
  hint,
  value,
  onChange,
  disabled,
}: {
  fieldKey: string;
  label: string;
  unit: string;
  hint: string;
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
}) {
  const numVal = parseFloat(value);
  const outOfRange = !isNaN(numVal) && isOutOfRange(fieldKey, numVal);

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <label className="font-mono text-[10px] uppercase tracking-[0.1em]" style={{ color: "#6B8A6A" }}>
          {label}
        </label>
        <span className="font-mono text-[10px] text-subtext/60">{hint}</span>
      </div>
      <div className="flex gap-2 items-center">
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="—"
          disabled={disabled}
          className="flex-1 px-3 py-2.5 rounded-input font-mono text-[13px] text-foreground placeholder:text-subtext bg-transparent outline-none transition-all bs-input-focus"
          style={{
            border: `1px solid ${outOfRange ? "rgba(251,146,60,.4)" : "rgba(74,222,128,.15)"}`,
          }}
        />
        <span className="font-mono text-[11px] text-subtext w-16 text-right shrink-0">{unit}</span>
      </div>
      {outOfRange && (
        <p className="font-mono text-[10.5px]" style={{ color: "#FB923C" }}>
          Valor fuera del rango de referencia — se guardará igualmente.
        </p>
      )}
    </div>
  );
}

function CSVPreviewTable({ parsed }: { parsed: ParsedCSV }) {
  const preview = parsed.rows.slice(0, 5);
  return (
    <div className="overflow-x-auto rounded-input" style={{ border: "1px solid rgba(74,222,128,.12)" }}>
      <table className="w-full text-left font-mono text-[11px]">
        <thead>
          <tr style={{ background: "rgba(74,222,128,.06)" }}>
            {parsed.headers.map((h) => (
              <th key={h} className="px-3 py-2 uppercase tracking-[0.06em]" style={{ color: "#6B8A6A" }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {preview.map((row, i) => (
            <tr key={i} style={{ borderTop: "1px solid rgba(74,222,128,.06)" }}>
              {parsed.headers.map((_, j) => (
                <td key={j} className="px-3 py-2 text-foreground">
                  {row[j] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PrivacyCard() {
  return (
    <div
      className="rounded-card px-5 py-5 flex flex-col gap-4"
      style={{
        background: "rgba(74,222,128,.05)",
        border: "1px solid rgba(74,222,128,.15)",
      }}
    >
      <div className="flex items-center gap-2">
        <ShieldCheck size={16} className="text-brand-green shrink-0" />
        <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-brand-green">
          Privacidad y seguridad
        </span>
      </div>
      <ul className="flex flex-col gap-2">
        {[
          "Encriptados con AES-256 antes de guardarse.",
          "Se borran automáticamente después de 180 días.",
          "Nunca se comparten ni se usan para entrenar modelos.",
          "Puedes eliminarlos en cualquier momento.",
        ].map((bullet) => (
          <li
            key={bullet}
            className="font-mono text-[11px] leading-[1.5] flex gap-2"
            style={{ color: "#6B8A6A" }}
          >
            <span className="text-brand-green shrink-0">·</span>
            {bullet}
          </li>
        ))}
      </ul>
    </div>
  );
}
