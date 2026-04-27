"use client";

import { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { ArrowLeft, Keyboard } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BarcodeScanner } from "@/components/scanner/BarcodeScanner";
import { PhotoCapture } from "@/components/scanner/PhotoCapture";
import { PhotoLoadingState } from "@/components/scanner/PhotoLoadingState";
import { scanBarcode, scanPhoto } from "@/lib/api/scan";
import { HttpError } from "@/lib/api/client";
import type { ScanResponse } from "@/lib/api/types";

type ActiveTab = "barcode" | "photo";
type BarcodeStatus = "idle" | "loading" | "not_found" | "error" | "permission_denied";
type PhotoStatus = "idle" | "error_read" | "error_process" | "error_net";

export default function ScanPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<ActiveTab>("barcode");
  const [barcodeStatus, setBarcodeStatus] = useState<BarcodeStatus>("idle");
  const [photoStatus, setPhotoStatus] = useState<PhotoStatus>("idle");
  const [manualBarcode, setManualBarcode] = useState("");
  const scanningRef = useRef(false);

  const barcodeMutation = useMutation({
    mutationFn: (barcode: string) => scanBarcode(barcode),
    onSuccess: (data, barcode) => {
      queryClient.setQueryData<ScanResponse>(["scan", barcode], data);
      router.push(`/scan/${barcode}`);
    },
    onError: (err) => {
      scanningRef.current = false;
      if (err instanceof HttpError && err.status === 404) {
        setBarcodeStatus("not_found");
      } else {
        setBarcodeStatus("error");
      }
    },
  });

  const photoMutation = useMutation({
    mutationFn: (base64: string) => scanPhoto(base64),
    onSuccess: (data) => {
      queryClient.setQueryData<ScanResponse>(["scan", data.product_barcode], data);
      router.push(`/scan/${encodeURIComponent(data.product_barcode)}?via=photo`);
    },
    onError: (err) => {
      if (err instanceof HttpError && err.status === 422) {
        setPhotoStatus("error_read");
      } else if (err instanceof HttpError && (err.status === 400 || err.status >= 500)) {
        setPhotoStatus("error_process");
      } else {
        setPhotoStatus("error_net");
      }
    },
  });

  const handleBarcodeDetect = useCallback(
    (barcode: string) => {
      if (scanningRef.current) return;
      // Chequea cache antes de llamar al backend (implementa 7.6 — cache por barcode)
      const cached = queryClient.getQueryData<ScanResponse>(["scan", barcode]);
      if (cached) {
        router.push(`/scan/${barcode}`);
        return;
      }
      scanningRef.current = true;
      setBarcodeStatus("loading");
      barcodeMutation.mutate(barcode);
    },
    [queryClient, router, barcodeMutation]
  );

  const handlePermissionDenied = useCallback(() => {
    setBarcodeStatus("permission_denied");
  }, []);

  const handlePhotoCapture = useCallback(
    (base64: string) => {
      photoMutation.mutate(base64);
    },
    [photoMutation]
  );

  function handleTabChange(value: string) {
    setActiveTab(value as ActiveTab);
    setBarcodeStatus("idle");
    setPhotoStatus("idle");
    scanningRef.current = false;
  }

  function handleManualSubmit(e: React.FormEvent) {
    e.preventDefault();
    const b = manualBarcode.trim();
    if (b.length < 8) return;
    handleBarcodeDetect(b);
  }

  function handleNotFoundGoPhoto() {
    setActiveTab("photo");
    setBarcodeStatus("idle");
    scanningRef.current = false;
  }

  const isBarcodeLoading = barcodeMutation.isPending;
  const isPhotoLoading = photoMutation.isPending;

  return (
    <div className="relative z-10 min-h-screen px-4 py-6 max-w-[640px] mx-auto">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 font-mono text-[11px] text-subtext hover:text-foreground transition-colors uppercase tracking-[0.08em] mb-6"
      >
        <ArrowLeft size={13} />
        volver
      </Link>

      <h1 className="font-sans font-bold text-xl text-foreground mb-1">Escanear producto</h1>
      <p className="font-mono text-[11px] text-subtext mb-6 uppercase tracking-[0.08em]">
        BARCODE · PHOTO · AI ANALYSIS
      </p>

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList
          className="w-full mb-6"
          style={{
            background: "rgba(74,222,128,.06)",
            border: "1px solid rgba(74,222,128,.1)",
          }}
        >
          <TabsTrigger
            value="barcode"
            className="flex-1 font-mono text-[12px] uppercase tracking-[0.06em] data-[state=active]:text-brand-green"
          >
            Código de barras
          </TabsTrigger>
          <TabsTrigger
            value="photo"
            className="flex-1 font-mono text-[12px] uppercase tracking-[0.06em] data-[state=active]:text-brand-green"
          >
            Foto de etiqueta
          </TabsTrigger>
        </TabsList>

        {/* ── Tab: Código de barras ── */}
        <TabsContent value="barcode">
          {barcodeStatus === "permission_denied" ? (
            <PermissionDeniedCard
              manualBarcode={manualBarcode}
              setManualBarcode={setManualBarcode}
              onManualSubmit={handleManualSubmit}
              loading={isBarcodeLoading}
            />
          ) : barcodeStatus === "not_found" ? (
            <NotFoundCard onTryPhoto={handleNotFoundGoPhoto} />
          ) : barcodeStatus === "error" ? (
            <InlineAlert
              message="Error al verificar el producto. Intenta de nuevo."
              onRetry={() => {
                setBarcodeStatus("idle");
                scanningRef.current = false;
              }}
            />
          ) : (
            <div className="flex flex-col gap-4">
              <BarcodeScanner
                onDetect={handleBarcodeDetect}
                onPermissionDenied={handlePermissionDenied}
                disabled={isBarcodeLoading}
              />

              {isBarcodeLoading && (
                <div className="flex items-center justify-center gap-2 py-3">
                  <Spinner />
                  <p className="font-mono text-[11px] text-subtext uppercase tracking-[0.08em]">
                    verificando producto…
                  </p>
                </div>
              )}

              {/* Input manual de barcode */}
              <form onSubmit={handleManualSubmit} className="flex gap-2 mt-1">
                <div className="relative flex-1">
                  <Keyboard
                    size={13}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-subtext pointer-events-none"
                  />
                  <input
                    type="text"
                    value={manualBarcode}
                    onChange={(e) => setManualBarcode(e.target.value)}
                    placeholder="O ingresa el código manualmente"
                    disabled={isBarcodeLoading}
                    className="w-full pl-8 pr-3 py-2.5 rounded-input font-mono text-[12px] text-foreground placeholder:text-subtext bg-transparent outline-none transition-all"
                    style={{ border: "1px solid rgba(74,222,128,.15)" }}
                  />
                </div>
                <button
                  type="submit"
                  disabled={isBarcodeLoading || manualBarcode.trim().length < 8}
                  className="px-4 py-2.5 rounded-button font-mono text-[12px] text-brand-green uppercase tracking-[0.08em] transition-all disabled:opacity-40"
                  style={{
                    background: "rgba(74,222,128,.12)",
                    border: "1px solid rgba(74,222,128,.3)",
                  }}
                >
                  ir
                </button>
              </form>
            </div>
          )}
        </TabsContent>

        {/* ── Tab: Foto de etiqueta ── */}
        <TabsContent value="photo">
          {isPhotoLoading ? (
            <PhotoLoadingState />
          ) : (
            <div className="flex flex-col gap-4">
              <PhotoCapture onCapture={handlePhotoCapture} disabled={false} />

              {photoStatus === "error_read" && (
                <InlineAlert
                  message="[ERROR_422] No pudimos leer la etiqueta. Intenta con mejor luz o ángulo."
                  onRetry={() => setPhotoStatus("idle")}
                />
              )}
              {photoStatus === "error_process" && (
                <InlineAlert
                  message="El servidor no pudo procesar la imagen. Intenta de nuevo."
                  onRetry={() => setPhotoStatus("idle")}
                />
              )}
              {photoStatus === "error_net" && (
                <InlineAlert
                  message="Error de conexión. Verifica tu red e intenta de nuevo."
                  onRetry={() => setPhotoStatus("idle")}
                />
              )}

              {/* [FASE 2] OFFContributeToggle — pendiente de implementar */}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ── Sub-components ─────────────────────────────────────── */

function PermissionDeniedCard({
  manualBarcode,
  setManualBarcode,
  onManualSubmit,
  loading,
}: {
  manualBarcode: string;
  setManualBarcode: (v: string) => void;
  onManualSubmit: (e: React.FormEvent) => void;
  loading: boolean;
}) {
  return (
    <div className="bs-card px-6 py-8 flex flex-col items-center gap-5">
      <Image
        src="/avatars/support.png"
        alt=""
        aria-hidden
        width={80}
        height={80}
        className="object-contain"
      />
      <div className="text-center">
        <p className="font-sans text-sm text-foreground font-semibold">Sin acceso a la cámara</p>
        <p className="font-mono text-[11px] text-subtext mt-1">
          Ingresa el código de barras manualmente
        </p>
      </div>
      <form onSubmit={onManualSubmit} className="w-full flex gap-2">
        <input
          type="text"
          value={manualBarcode}
          onChange={(e) => setManualBarcode(e.target.value)}
          placeholder="ej. 3017620422003"
          disabled={loading}
          className="flex-1 px-3 py-2.5 rounded-input font-mono text-[12px] text-foreground placeholder:text-subtext bg-transparent outline-none"
          style={{ border: "1px solid rgba(74,222,128,.15)" }}
          autoFocus
        />
        <button
          type="submit"
          disabled={loading || manualBarcode.trim().length < 8}
          className="px-4 py-2.5 rounded-button font-mono text-[12px] text-brand-green uppercase tracking-[0.08em] disabled:opacity-40"
          style={{
            background: "rgba(74,222,128,.12)",
            border: "1px solid rgba(74,222,128,.3)",
          }}
        >
          {loading ? <Spinner /> : "ir"}
        </button>
      </form>
    </div>
  );
}

function NotFoundCard({ onTryPhoto }: { onTryPhoto: () => void }) {
  return (
    <div className="bs-card px-6 py-8 flex flex-col items-center gap-5 text-center">
      <p className="font-sans text-base text-foreground font-semibold">
        No encontramos este producto
      </p>
      <p className="font-mono text-[12px] text-subtext max-w-[280px] leading-[1.6]">
        Este código de barras no está en la base de datos. Puedes intentar analizando la foto de la
        etiqueta.
      </p>
      <button
        onClick={onTryPhoto}
        className="px-6 py-3 rounded-button font-mono text-[12px] uppercase tracking-[0.08em] text-brand-green transition-all bs-glow-green hover:bs-glow-green-strong"
        style={{
          background: "rgba(74,222,128,.12)",
          border: "1px solid rgba(74,222,128,.3)",
        }}
      >
        Intentar con foto →
      </button>
    </div>
  );
}

function InlineAlert({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col gap-2">
      <div
        className="px-4 py-3 rounded-input font-mono text-[11.5px]"
        style={{
          background: "rgba(248,113,113,.08)",
          border: "1px solid rgba(248,113,113,.3)",
          color: "#F87171",
        }}
        role="alert"
      >
        {message}
      </div>
      <button
        onClick={onRetry}
        className="self-start font-mono text-[11px] text-brand-teal hover:underline"
      >
        reintentar
      </button>
    </div>
  );
}

function Spinner() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="animate-spin">
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
