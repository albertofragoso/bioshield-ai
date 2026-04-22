"use client";

import Image from "next/image";
import { Dialog, DialogContent } from "@/components/ui/dialog";

interface SessionExpiredDialogProps {
  open: boolean;
  onConfirm: () => void;
}

export function SessionExpiredDialog({ open, onConfirm }: SessionExpiredDialogProps) {
  return (
    <Dialog open={open}>
      <DialogContent
        showCloseButton={false}
        className="max-w-[360px] flex flex-col items-center gap-5 py-8 text-center bs-card border-0"
        style={{ border: "1px solid rgba(74,222,128,.18)" }}
      >
        <Image
          src="/avatars/main.png"
          alt=""
          aria-hidden
          width={80}
          height={80}
          className="object-contain"
        />

        <div className="flex flex-col gap-2">
          <p className="font-sans font-semibold text-xl text-foreground">
            sesión expirada
          </p>
          <p className="font-mono text-[12px] text-subtext leading-relaxed">
            Tu sesión expiró por inactividad.
            <br />
            Inicia sesión de nuevo para continuar.
          </p>
        </div>

        <button
          onClick={onConfirm}
          className="w-full rounded-button py-[14px] font-mono text-[13px] font-semibold uppercase tracking-[0.12em] text-brand-green bs-glow-green hover:bs-glow-green-strong transition-all duration-200"
          style={{
            background: "rgba(74,222,128,.15)",
            border: "1.5px solid #4ADE80",
          }}
        >
          entrar de nuevo
        </button>
      </DialogContent>
    </Dialog>
  );
}
