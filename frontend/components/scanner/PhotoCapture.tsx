"use client";

import { useRef, useState, useCallback } from "react";
import { ImagePlus, Upload } from "lucide-react";

const MAX_BYTES = 10 * 1024 * 1024;

interface Props {
  onCapture: (base64: string) => void;
  disabled?: boolean;
}

export function PhotoCapture({ onCapture, disabled = false }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const [sizeError, setSizeError] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);

  const processFile = useCallback(
    (file: File) => {
      setSizeError(false);
      if (file.size > MAX_BYTES) {
        setSizeError(true);
        return;
      }
      const reader = new FileReader();
      reader.onload = (e) => {
        const raw = e.target?.result as string;
        const base64 = raw.split(",")[1];
        setPreview(raw);
        onCapture(base64);
      };
      reader.readAsDataURL(file);
    },
    [onCapture],
  );

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) processFile(file);
    e.target.value = "";
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    const file = e.dataTransfer.files?.[0];
    if (file) processFile(file);
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Dropzone */}
      <button
        type="button"
        onClick={() => !disabled && fileInputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        disabled={disabled}
        className="relative w-full rounded-card flex flex-col items-center justify-center gap-3 py-10 px-6 transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        style={{
          border: `2px dashed ${dragging ? "rgba(74,222,128,.6)" : "rgba(74,222,128,.3)"}`,
          background: dragging ? "rgba(74,222,128,.06)" : "rgba(74,222,128,.03)",
        }}
      >
        {preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={preview}
            alt="vista previa"
            className="max-h-[180px] object-contain rounded-[8px]"
          />
        ) : (
          <>
            <ImagePlus size={32} style={{ color: "#6B8A6A" }} />
            <div className="text-center">
              <p className="font-sans text-sm text-foreground">Arrastra o selecciona foto de la etiqueta</p>
              <p className="font-mono text-[11px] text-subtext mt-1">JPG · PNG · WEBP · máx 10 MB</p>
            </div>
          </>
        )}
      </button>

      {sizeError && (
        <p
          className="font-mono text-[11.5px] px-3 py-2 rounded-input"
          style={{
            background: "rgba(248,113,113,.08)",
            border: "1px solid rgba(248,113,113,.3)",
            color: "#F87171",
          }}
          role="alert"
        >
          [ERROR_413] Imagen muy grande (máx 10 MB).
        </p>
      )}

      {/* Botón cámara — solo en mobile */}
      <button
        type="button"
        onClick={() => !disabled && cameraInputRef.current?.click()}
        disabled={disabled}
        className="sm:hidden flex items-center justify-center gap-2 w-full py-3 rounded-button font-mono text-[12px] uppercase tracking-[0.08em] text-brand-green transition-all disabled:opacity-50"
        style={{
          background: "rgba(74,222,128,.08)",
          border: "1px solid rgba(74,222,128,.25)",
        }}
      >
        <Upload size={14} />
        Tomar foto
      </button>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="sr-only"
        onChange={handleFileChange}
      />
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        onChange={handleFileChange}
      />
    </div>
  );
}
