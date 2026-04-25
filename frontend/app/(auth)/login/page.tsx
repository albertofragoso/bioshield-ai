"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { Mail, Lock, WifiOff } from "lucide-react";
import { login } from "@/lib/api/auth";
import { HttpError } from "@/lib/api/client";
import { AuthField } from "@/components/auth/AuthField";
import { AuthAlert } from "@/components/auth/AuthAlert";

type FormError = "401" | "429" | "network" | null;

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [formError, setFormError] = useState<FormError>(null);

  const { mutate, isPending } = useMutation({
    mutationFn: login,
    onSuccess: () => router.push("/"),
    onError: (error: unknown) => {
      if (error instanceof HttpError) {
        if (error.status === 401) setFormError("401");
        else if (error.status === 429) setFormError("429");
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
        <div
          className="bs-card relative overflow-hidden px-[36px] py-[40px] max-sm:px-[16px] max-sm:py-[28px]"
        >
          {/* Corner accents */}
          <span className="bs-corner bs-corner-tl" />
          <span className="bs-corner bs-corner-tr" />
          <span className="bs-corner bs-corner-bl" />
          <span className="bs-corner bs-corner-br" />

          {/* Avatar */}
          <div className="flex flex-col items-center gap-3 mb-6">
            <div className="animate-wobble [transform-origin:bottom_center]">
              <Image
                src="/avatars/main.png"
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
            {/* API errors */}
            {formError === "401" && <AuthAlert type="401" />}
            {formError === "429" && <AuthAlert type="429" />}

            {/* Network error toast inline */}
            {formError === "network" && (
              <div
                className="flex items-center gap-2 rounded-input px-4 py-3 font-mono text-[13px]"
                style={{
                  background: "#111",
                  border: "1px solid rgba(245,158,11,.3)",
                  color: "#F59E0B",
                }}
                role="alert"
              >
                <WifiOff size={14} />
                sin_conexion_al_servidor
              </div>
            )}

            {/* Validation error */}
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

            <AuthField
              label="Contraseña"
              type="password"
              value={password}
              onChange={setPassword}
              disabled={isPending}
              icon={Lock}
              placeholder="mínimo 8 caracteres"
              autoComplete="current-password"
            />

            {/* Forgot password */}
            <div className="flex justify-end">
              <span className="font-mono text-[10.5px] text-brand-teal tracking-[0.04em] opacity-80 cursor-not-allowed">
                ¿Olvidaste tu contraseña?
              </span>
            </div>

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
                  verificando…
                </span>
              ) : (
                "⟶ entrar"
              )}
            </button>
          </form>

          {/* Register link */}
          <p className="mt-5 text-center font-mono text-[11px]">
            <span className="text-subtext">sin cuenta?</span>{" "}
            <Link href="/register" className="text-brand-amber font-semibold hover:opacity-80 transition-opacity">
              regístrate →
            </Link>
          </p>

          {/* Metadata footer */}
          <p
            className="mt-4 text-center font-mono text-[9px]"
            style={{ color: "rgba(74,222,128,.2)" }}
          >
            v1.0.0 · /login · POST /auth/login
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
