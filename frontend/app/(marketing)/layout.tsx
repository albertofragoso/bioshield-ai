import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "BioShield AI — Nutrición inteligente",
  description:
    "Escanea cualquier producto y descubre si sus aditivos son compatibles con tus análisis de laboratorio.",
};

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <header className="fixed top-0 z-50 w-full flex items-center justify-between px-6 py-4 bg-background/80 backdrop-blur-sm border-b border-border">
        <div className="flex items-center gap-1">
          <span className="font-display text-xl text-brand-green">BioShield</span>
          <span className="font-sans font-bold text-lg text-brand-amber">AI</span>
        </div>
        <a
          href="/login"
          className="font-mono text-[12px] text-subtext hover:text-foreground transition-colors"
        >
          Entrar →
        </a>
      </header>
      <main className="pt-16">{children}</main>
    </>
  );
}
