"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { Mail, Lock, ShieldCheck } from "lucide-react";
import { register, login } from "@/lib/api/auth";
import { HttpError } from "@/lib/api/client";
import { AuthField } from "@/components/auth/AuthField";
import { AuthAlert } from "@/components/auth/AuthAlert";

type FormError = "409" | "network" | null;

// Evalúa fuerza de la contraseña: retorna 0 (vacía), 1 (corta), 2 (media), 3 (fuerte)
function passwordStrength(pw: string): 0 | 1 | 2 | 3 {
  if (pw.length === 0) return 0;
  if (pw.length < 6) return 1;
  const hasVariety = /[A-Z]/.test(pw) || /[0-9]/.test(pw) || /[^a-zA-Z0-9]/.test(pw);
  if (pw.length >= 10 && hasVariety) return 3;
  return 2;
}

const STRENGTH_CONFIG = {
  0: { width: "0%", color: "transparent" },
  1: { width: "33%", color: "#F87171" },
  2: { width: "66%", color: "#F59E0B" },
  3: { width: "100%", color: "#4ADE80" },
} as const;

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [formError, setFormError] = useState<FormError>(null);

  const strength = passwordStrength(password);
  const { width: strengthWidth, color: strengthColor } = STRENGTH_CONFIG[strength];

  const { mutate, isPending } = useMutation({
    mutationFn: async (body: { email: string; password: string }) => {
      await register(body);
      // Auto-login inmediato post-register
      await login(body);
    },
    onSuccess: () => router.push("/"),
    onError: (error: unknown) => {
      if (error instanceof HttpError) {
        if (error.status === 409) setFormError("409");
        else setFormError("network");
      } else {
        setFormError("network");
      }
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setValidationError(null);
    setFormError(null);

    if (!email.includes("@")) {
      setValidationError("Ingresa un email válido.");
      return;
    }
    if (password.length < 8) {
      setValidationError("La contraseña debe tener al menos 8 caracteres.");
      return;
    }
    if (!accepted) {
      setValidationError("Debes aceptar los términos para continuar.");
      return;
    }

    mutate({ email, password });
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-8 relative z-10">
      <div className="relative w-full max-w-[420px]">
        {/* Glow superior */}
        <div
          className="absolute left-1/2 -translate-x-1/2 pointer-events-none"
          style={{
            top: "-60px",
            width: "260px",
            height: "140px",
            background: "radial-gradient(ellipse, rgba(74,222,128,.1) 0%, transparent 70%)",
          }}
        />

        {/* Card */}
        <div className="bs-card relative overflow-hidden px-[36px] py-[40px] max-sm:px-[16px] max-sm:py-[28px]">
          {/* Corner accents */}
          <span className="bs-corner bs-corner-tl" />
          <span className="bs-corner bs-corner-tr" />
          <span className="bs-corner bs-corner-bl" />
          <span className="bs-corner bs-corner-br" />

          {/* Avatar */}
          <div className="flex flex-col items-center gap-3 mb-6">
            <div className="animate-wobble [transform-origin:bottom_center]">
              <Image
                src="/avatars/welcome.png"
                alt="BioShield mascota"
                width={140}
                height={140}
                className="object-contain animate-pulse-glow"
                priority
              />
            </div>

            {/* Wordmark */}
            <div className="text-center">
              <h1 className="inline-flex items-baseline gap-[6px]">
                <span
                  className="font-display text-[28px] text-brand-green"
                  style={{ textShadow: "0 0 30px rgba(74,222,128,.5)" }}
                >
                  BioShield
                </span>
                <span className="font-sans font-bold text-[26px] text-brand-amber tracking-[0.06em]">
                  AI
                </span>
              </h1>
              <p className="font-mono text-[9.5px] text-subtext tracking-[0.18em] uppercase mt-1">
                hack your nutrition ✦ protect your biology
              </p>
            </div>

            {/* Divider */}
            <div
              className="w-full h-px mt-2"
              style={{ background: "linear-gradient(90deg, transparent, rgba(74,222,128,.2), transparent)" }}
            />
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
            {formError === "409" && <AuthAlert type="409" />}
            {formError === "network" && (
              <div
                className="rounded-input px-4 py-3 font-mono text-[11.5px]"
                style={{
                  background: "rgba(248,113,113,0.08)",
                  border: "1px solid rgba(248,113,113,0.3)",
                  color: "#F87171",
                }}
                role="alert"
              >
                Error de conexión. Intenta de nuevo.
              </div>
            )}

            {validationError && (
              <p className="font-mono text-[11px] text-[#F87171]">{validationError}</p>
            )}

            <AuthField
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              disabled={isPending}
              icon={Mail}
              placeholder="tu@email.com"
              autoComplete="email"
            />

            {/* Password con barra de fuerza */}
            <div className="flex flex-col gap-1.5">
              <AuthField
                label="Contraseña"
                type="password"
                value={password}
                onChange={setPassword}
                disabled={isPending}
                icon={Lock}
                placeholder="mínimo 8 caracteres"
                autoComplete="new-password"
              />
              {/* Barra de fuerza */}
              <div
                className="h-[3px] w-full rounded-full overflow-hidden"
                style={{ background: "rgba(74,222,128,0.08)" }}
              >
                <div
                  className="h-full rounded-full"
                  style={{
                    width: strengthWidth,
                    background: strengthColor,
                    transition: "width 0.3s ease, background 0.3s ease",
                  }}
                />
              </div>
            </div>

            {/* Privacy note */}
            <div
              className="flex gap-3 items-start py-2"
              style={{
                borderLeft: "2px solid rgba(74,222,128,.3)",
                paddingLeft: "10px",
              }}
            >
              <ShieldCheck size={14} className="text-brand-green mt-[1px] shrink-0" />
              <p className="font-mono text-[10px] text-subtext leading-[1.6]">
                Tus biomarcadores se encriptan con AES-256 y se borran automáticamente
                después de 180 días. Nunca los compartimos.
              </p>
            </div>

            {/* Checkbox de términos */}
            <label className="flex items-start gap-2.5 cursor-pointer group">
              <div className="relative mt-[2px] shrink-0">
                <input
                  type="checkbox"
                  checked={accepted}
                  onChange={(e) => setAccepted(e.target.checked)}
                  disabled={isPending}
                  className="sr-only"
                />
                <div
                  className="w-4 h-4 rounded-[4px] flex items-center justify-center transition-all duration-200"
                  style={{
                    background: accepted ? "rgba(74,222,128,0.15)" : "rgba(0,0,0,0.4)",
                    border: accepted ? "1.5px solid #4ADE80" : "1.5px solid rgba(74,222,128,0.3)",
                  }}
                >
                  {accepted && (
                    <svg width="9" height="7" viewBox="0 0 9 7" fill="none">
                      <path d="M1 3.5L3.5 6L8 1" stroke="#4ADE80" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </div>
              </div>
              <span className="font-mono text-[11px] text-subtext select-none">
                acepto los términos y la política de datos médicos
              </span>
            </label>

            {/* CTA */}
            <button
              type="submit"
              disabled={isPending}
              className="w-full rounded-button py-[15px] font-mono text-[13px] font-semibold uppercase tracking-[0.12em] text-brand-green transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed bs-glow-green hover:bs-glow-green-strong"
              style={{
                background: "rgba(74,222,128,.15)",
                border: "1.5px solid #4ADE80",
              }}
            >
              {isPending ? (
                <span className="flex items-center justify-center gap-2">
                  <Spinner />
                  creando cuenta…
                </span>
              ) : (
                "⟶ crear cuenta"
              )}
            </button>
          </form>

          {/* Login link */}
          <p className="mt-5 text-center font-mono text-[11px]">
            <span className="text-subtext">¿ya tienes cuenta?</span>{" "}
            <Link href="/login" className="text-brand-amber font-semibold hover:opacity-80 transition-opacity">
              entra →
            </Link>
          </p>

          {/* Metadata footer */}
          <p
            className="mt-4 text-center font-mono text-[9px]"
            style={{ color: "rgba(74,222,128,.2)" }}
          >
            v1.0.0 · /register · POST /auth/register
          </p>
        </div>
      </div>
    </div>
  );
}

function Spinner() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="animate-spin">
      <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.5" strokeDasharray="22" strokeDashoffset="10" strokeLinecap="round" />
    </svg>
  );
}
