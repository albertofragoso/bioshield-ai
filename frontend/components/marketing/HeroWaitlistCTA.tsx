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
      toast.error(result.error.errors[0].message);
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

  if (done) {
    return (
      <p className="font-mono text-[12px] text-brand-green">
        Estás en la lista. Te avisamos pronto.
      </p>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 w-full max-w-sm">
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
  );
}
