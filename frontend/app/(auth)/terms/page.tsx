import fs from "fs";
import Link from "next/link";
import Image from "next/image";
import { marked } from "marked";
import { getLegalDocPath } from "@/lib/legal-path";

export default async function TermsPage() {
  const raw = fs.readFileSync(getLegalDocPath("terms.md"), "utf-8");
  // Suppress h1 — title is already rendered in JSX above
  const renderer = new marked.Renderer();
  const origHeading = renderer.heading.bind(renderer);
  renderer.heading = (token) => (token.depth === 1 ? "" : origHeading(token));
  const html = await marked(raw, { renderer });

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-8 relative z-10">
      <div className="relative w-full max-w-[560px]">
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
          <span className="bs-corner bs-corner-tl" />
          <span className="bs-corner bs-corner-tr" />
          <span className="bs-corner bs-corner-bl" />
          <span className="bs-corner bs-corner-br" />

          {/* Avatar */}
          <div className="flex flex-col items-center gap-3 mb-6">
            <Image
              src="/avatars/profile.png"
              alt="BioShield perfil"
              width={100}
              height={107}
              className="object-contain"
              priority
            />
            <div className="text-center">
              <h1 className="font-sans font-bold text-[22px] text-foreground">
                Términos y Condiciones
              </h1>
              <p className="font-mono text-[10px] text-subtext tracking-[0.1em] uppercase mt-1">
                Última actualización: mayo 2026
              </p>
            </div>
            <div
              className="w-full h-px mt-1"
              style={{
                background: "linear-gradient(90deg, transparent, rgba(74,222,128,.2), transparent)",
              }}
            />
          </div>

          {/* Markdown content */}
          <div
            className="legal-content font-mono text-[12px] leading-[1.7] text-subtext"
            dangerouslySetInnerHTML={{ __html: html }}
          />

          {/* Back link */}
          <div className="mt-8 text-center">
            <Link
              href="/register"
              className="font-mono text-[11px] text-brand-amber hover:opacity-80 transition-opacity"
            >
              ← volver al registro
            </Link>
          </div>

          <p
            className="mt-4 text-center font-mono text-[9px]"
            style={{ color: "rgba(74,222,128,.2)" }}
          >
            v1.0.0 · /terms · legal@bioshield.ai
          </p>
        </div>
      </div>
    </div>
  );
}
