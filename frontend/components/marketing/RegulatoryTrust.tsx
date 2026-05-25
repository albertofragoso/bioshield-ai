"use client";

import { Shield } from "@phosphor-icons/react/dist/csr/Shield";
import { BookOpen } from "@phosphor-icons/react/dist/csr/BookOpen";
import { Globe } from "@phosphor-icons/react/dist/csr/Globe";
import type { Icon } from "@phosphor-icons/react";

const N_INGREDIENTS = 8_000; // TODO: verify with SELECT COUNT(*) FROM ingredients before deploy

type Source = {
  name: string;
  url: string;
  Icon: Icon;
};

const SOURCES: Source[] = [
  {
    name: "FDA EAFUS",
    url: "https://www.fda.gov/food/food-additives-petitions/food-additive-status-list",
    Icon: Shield,
  },
  {
    name: "EFSA OpenFoodTox",
    url: "https://www.efsa.europa.eu/en/data/data-open-food-tox",
    Icon: BookOpen,
  },
  { name: "Codex Alimentarius", url: "https://www.fao.org/fao-who-codexalimentarius", Icon: Globe },
];

export function RegulatoryTrust() {
  return (
    <div className="max-w-4xl mx-auto px-6 text-center">
      <p className="font-mono text-[10px] text-brand-green uppercase tracking-[0.18em] mb-4 opacity-80">
        Fuentes de datos
      </p>
      <h2 className="font-sans text-2xl font-bold text-foreground mb-8">
        Información de bases regulatorias públicas
      </h2>

      <div className="flex flex-wrap justify-center gap-3 mb-10">
        {SOURCES.map((source) => (
          <a
            key={source.name}
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 border border-border rounded-card px-4 py-3 font-mono text-[11px] text-subtext transition-colors"
            style={{ background: "var(--surface)" }}
            onMouseEnter={(e) => (e.currentTarget.style.borderColor = "rgba(74,222,128,.4)")}
            onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border)")}
          >
            <source.Icon weight="duotone" size={16} color="#4ADE80" />
            <span>{source.name}</span>
          </a>
        ))}
      </div>

      <div
        className="inline-flex items-center gap-3 border border-border rounded-full px-6 py-3"
        style={{ background: "var(--surface)" }}
      >
        <span className="font-mono text-2xl font-bold text-brand-green">
          {N_INGREDIENTS.toLocaleString("es-MX")}
        </span>
        <span className="font-mono text-[12px] text-subtext">ingredientes indexados</span>
      </div>
    </div>
  );
}
