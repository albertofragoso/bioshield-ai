"use client";

import { useState } from "react";
import { z } from "zod";
import { toast } from "sonner";

const schema = z.object({
  email: z.string().email("Email inválido"),
});

export function HeroWaitlistCTA() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const result = schema.safeParse({ email });
    if (!result.success) {
      toast.error(result.error.issues[0].message);
      return;
    }

    setLoading(true);
    try {
      const resp = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/waitlist`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email,
            consent: true,
            turnstile_token: "hero-inline",
          }),
        }
      );

      if (resp.status === 409) {
        toast.info("Ya estás en la lista, te avisamos pronto.");
        setDone(true);
        return;
      }

      if (!resp.ok) throw new Error("Error al registrarse");

      toast.success("Listo, te avisamos cuando abramos el beta.");
      setDone(true);
    } catch {
      toast.error("Algo salió mal. Intentá de nuevo.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center gap-4">
      <style>{`
        @keyframes hero-fade-up {
          from { opacity: 0; transform: translateY(16px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @media (prefers-reduced-motion: no-preference) {
          .hero-reveal {
            opacity: 0;
            animation: hero-fade-up 0.55s ease forwards;
          }
        }
      `}</style>

      {/* Form / done state */}
      {done ? (
        <p className="font-mono text-[12px] text-brand-green">
          Estás en la lista. Te avisamos pronto.
        </p>
      ) : (
        <form
          onSubmit={handleSubmit}
          className="hero-reveal flex gap-2 w-full max-w-sm"
          style={{ animationDelay: "0.1s" }}
        >
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="tu@email.com"
            required
            className="flex-1 px-4 py-2.5 rounded-input font-mono text-[12px] text-foreground placeholder:text-subtext focus:outline-none transition-colors"
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
            onFocus={(e) => (e.target.style.borderColor = "#4ade80")}
            onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
          />
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2.5 rounded-button font-mono text-[12px] font-semibold uppercase tracking-[0.08em] text-brand-green disabled:opacity-60 transition-all shrink-0 hover:opacity-90"
            style={{ background: "rgba(74,222,128,.15)", border: "1.5px solid #4ade80" }}
          >
            {loading ? "..." : "Unirme"}
          </button>
        </form>
      )}

      {/* Social proof — always visible */}
      <div
        className="hero-reveal flex items-center gap-2"
        style={{ animationDelay: "0.25s" }}
        aria-label="Más de 1200 personas en la lista de espera"
      >
        {/* Avatar stack */}
        <div className="flex items-center">
          <span className="w-5 h-5 rounded-full bg-gradient-to-br from-teal-400 to-teal-600 inline-block" />
          <span className="w-5 h-5 rounded-full bg-gradient-to-br from-teal-400 to-teal-600 inline-block ml-[-6px]" />
          <span className="w-5 h-5 rounded-full bg-gradient-to-br from-teal-400 to-teal-600 inline-block ml-[-6px]" />
        </div>
        <span className="text-xs text-neutral-500">+1,200 personas ya en lista · Sin spam</span>
      </div>
    </div>
  );
}
