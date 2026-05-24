"use client";

import { useEffect, useState } from "react";
import { z } from "zod";
import { toast } from "sonner";

const schema = z.object({
  email: z.string().email("Email inválido"),
  consent: z.literal(true, "El consentimiento es obligatorio"),
});

const toRange = (total: number): string => {
  if (total < 50) return "+40";
  if (total < 100) return "+80";
  if (total < 200) return "+100";
  if (total < 500) return "+200";
  return `+${Math.floor(total / 100) * 100}`;
};

export function WaitlistHero() {
  const [form, setForm] = useState({
    email: "",
    name: "",
    signup_intent: "",
    consent: false,
  });
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/waitlist/count`)
      .then((r) => r.json())
      .then(({ total }: { total: number }) => setCount(total))
      .catch(() => null);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const result = schema.safeParse({ email: form.email, consent: form.consent || undefined });
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
            email: form.email,
            name: form.name || undefined,
            signup_intent: form.signup_intent || undefined,
            consent: true,
            turnstile_token: "dev-bypass",
          }),
        }
      );

      if (resp.status === 409) {
        toast.info("Ya estás en la lista, te avisamos pronto.");
        setDone(true);
        return;
      }
      if (!resp.ok) throw new Error("Error");

      const data = (await resp.json()) as { total: number };
      setCount(data.total);
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
      <div className="text-center py-12">
        <div className="text-4xl mb-4">🎉</div>
        <h3 className="font-sans text-2xl font-bold text-brand-green mb-2">Estás en la lista</h3>
        <p className="font-mono text-[12px] text-subtext">Te avisamos cuando abramos el beta.</p>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto px-6 text-center">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-brand-green mb-4 opacity-80">
        Tu guardián nutricional con IA
      </p>
      <h2 className="font-sans text-3xl lg:text-4xl font-bold text-foreground mb-4">
        Sé de los primeros en probarlo.
      </h2>

      {count !== null && (
        <p className="font-mono text-[12px] text-subtext mb-8">
          <span className="text-brand-green font-bold">{toRange(count)}</span> personas ya están en
          la lista
        </p>
      )}

      <form onSubmit={handleSubmit} className="space-y-4 text-left">
        <input
          type="email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          placeholder="tu@email.com"
          required
          className="w-full px-4 py-3 rounded-input font-mono text-[12px] text-foreground placeholder:text-subtext focus:outline-none transition-colors"
          style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
        />

        <input
          type="text"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="Nombre (opcional)"
          className="w-full px-4 py-3 rounded-input font-mono text-[12px] text-foreground placeholder:text-subtext focus:outline-none transition-colors"
          style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
        />

        <select
          value={form.signup_intent}
          onChange={(e) => setForm({ ...form, signup_intent: e.target.value })}
          className="w-full px-4 py-3 rounded-input font-mono text-[12px] text-subtext focus:outline-none transition-colors"
          style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
        >
          <option value="">¿Para qué lo usarías? (opcional)</option>
          <option value="salud_personal">Salud personal o familiar</option>
          <option value="interes_tecnico">Interés técnico / profesional</option>
          <option value="otro">Otro</option>
        </select>

        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={form.consent}
            onChange={(e) => setForm({ ...form, consent: e.target.checked })}
            required
            className="mt-1"
            style={{ accentColor: "#4ade80" }}
          />
          <span className="font-mono text-[10px] text-subtext leading-relaxed">
            Acepto recibir invitación al beta Q2 2026 y el tratamiento de mis datos personales
            conforme a la{" "}
            <a href="/privacy" className="underline hover:text-foreground transition-colors">
              LFPDPPP México
            </a>
            .
          </span>
        </label>

        <button
          type="submit"
          disabled={loading || !form.consent}
          className="w-full py-3 rounded-button font-mono text-[12px] font-semibold uppercase tracking-[0.08em] text-brand-green disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          style={{ background: "rgba(74,222,128,.15)", border: "1.5px solid #4ade80" }}
        >
          {loading ? "Registrando..." : "Unirme a la lista"}
        </button>

        <p className="font-mono text-[10px] text-subtext text-center">
          Cero spam. Datos cifrados AES-256. Puedes pedir borrado cuando quieras.
        </p>
      </form>
    </div>
  );
}
