const FOOTER_LINKS = [
  { label: "Privacidad", href: "/privacy" },
  { label: "Términos", href: "/terms" },
  { label: "GitHub", href: "https://github.com/TBD/bioshield", external: true },
  { label: "press@bioshield.mx", href: "mailto:press@bioshield.mx", external: true },
];

export function MarketingFooter() {
  return (
    <footer className="border-t border-border py-10 px-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
          <span className="font-display text-brand-green text-xl">BioShield</span>

          <nav className="flex flex-wrap justify-center gap-x-6 gap-y-2">
            {FOOTER_LINKS.map((link) => (
              <a
                key={link.label}
                href={link.href}
                target={link.external ? "_blank" : undefined}
                rel={link.external ? "noopener noreferrer" : undefined}
                className="font-mono text-[11px] text-subtext hover:text-foreground transition-colors"
              >
                {link.label}
              </a>
            ))}
          </nav>

          <p className="font-mono text-[10px] text-subtext">© 2026 BioShield AI · Hecho en MX</p>
        </div>

        <p
          className="mt-6 text-center font-mono text-[10px] text-subtext leading-relaxed max-w-xl mx-auto"
          style={{ opacity: 0.6 }}
        >
          Herramienta educativa e informativa. No sustituye la consulta médica profesional. No
          avalada por COFEPRIS ni FDA. Información basada en bases de datos regulatorias públicas.
        </p>
      </div>
    </footer>
  );
}
