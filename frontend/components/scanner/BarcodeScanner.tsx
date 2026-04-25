"use client";

import { useEffect, useRef, useState, useCallback } from "react";

interface Props {
  onDetect: (barcode: string) => void;
  onPermissionDenied: () => void;
  disabled?: boolean;
}

export function BarcodeScanner({ onDetect, onPermissionDenied, disabled = false }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const controlsRef = useRef<{ stop: () => void } | null>(null);
  const [flashing, setFlashing] = useState(false);
  const detectedRef = useRef(false);

  const handleDetect = useCallback(
    (barcode: string) => {
      if (detectedRef.current || disabled) return;
      detectedRef.current = true;
      setFlashing(true);
      setTimeout(() => {
        setFlashing(false);
        onDetect(barcode);
      }, 300);
    },
    [disabled, onDetect],
  );

  useEffect(() => {
    if (disabled || !videoRef.current) return;
    detectedRef.current = false;
    let cancelled = false;

    async function start() {
      try {
        const { BrowserMultiFormatReader } = await import("@zxing/browser");
        if (cancelled || !videoRef.current) return;

        const reader = new BrowserMultiFormatReader();

        const controls = await reader.decodeFromVideoDevice(
          undefined,
          videoRef.current,
          (result) => {
            if (!cancelled && result) handleDetect(result.getText());
          },
        );
        if (!cancelled) controlsRef.current = controls;
      } catch (err: unknown) {
        if (cancelled) return;
        if (
          err instanceof DOMException &&
          (err.name === "NotAllowedError" || err.name === "PermissionDeniedError")
        ) {
          onPermissionDenied();
        }
      }
    }

    start();

    return () => {
      cancelled = true;
      controlsRef.current?.stop();
      controlsRef.current = null;
    };
  }, [disabled, handleDetect, onPermissionDenied]);

  return (
    <div
      className="relative w-full mx-auto overflow-hidden rounded-card"
      style={{ maxWidth: "480px", aspectRatio: "4/3" }}
    >
      <video ref={videoRef} className="w-full h-full object-cover" muted playsInline />

      {/* Overlay con ventana recortada */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute inset-x-0 top-0 h-[20%]" style={{ background: "rgba(0,0,0,.55)" }} />
        <div className="absolute inset-x-0 bottom-0 h-[20%]" style={{ background: "rgba(0,0,0,.55)" }} />
        <div className="absolute left-0 top-[20%] bottom-[20%] w-[8%]" style={{ background: "rgba(0,0,0,.55)" }} />
        <div className="absolute right-0 top-[20%] bottom-[20%] w-[8%]" style={{ background: "rgba(0,0,0,.55)" }} />

        {/* Ventana del scanner */}
        <div
          className="absolute top-[20%] left-[8%] right-[8%] bottom-[20%] transition-colors duration-300 overflow-hidden"
          style={{
            border: "2px solid #4ADE80",
            borderRadius: "8px",
            background: flashing ? "rgba(74,222,128,.18)" : "transparent",
          }}
        >
          {/* Línea láser */}
          {!disabled && (
            <div
              className="absolute inset-x-0 h-[2px]"
              style={{
                background: "linear-gradient(90deg, transparent, #4ADE80, transparent)",
                animation: "scan-line 2s linear infinite",
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
