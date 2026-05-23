const GITHUB_URL = "https://github.com/TBD/bioshield"; // actualizar antes de deploy

const STACK_ITEMS = [
  { name: "Next.js", desc: "Frontend" },
  { name: "FastAPI", desc: "Backend" },
  { name: "LangGraph", desc: "Orquestación IA" },
  { name: "Gemini", desc: "Visión + LLM" },
  { name: "ChromaDB", desc: "Vector Store" },
];

export function StackStrip() {
  return (
    <div className="max-w-4xl mx-auto px-6 text-center">
      <p className="font-mono text-[10px] text-subtext uppercase tracking-[0.18em] mb-4 opacity-60">
        Para curiosos técnicos
      </p>
      <h2 className="font-sans text-2xl font-bold text-foreground mb-4">
        Construido con tecnología abierta
      </h2>
      <p className="font-mono text-[12px] text-subtext mb-10">
        Para que puedas auditar cómo funciona.
      </p>

      <div className="flex flex-wrap justify-center gap-3 mb-8">
        {STACK_ITEMS.map((item) => (
          <div
            key={item.name}
            className="border border-border rounded-card px-4 py-2 text-center"
            style={{ background: "var(--surface)" }}
          >
            <div className="font-sans text-sm font-medium text-foreground">{item.name}</div>
            <div className="font-mono text-[10px] text-subtext">{item.desc}</div>
          </div>
        ))}
      </div>

      <a
        href={GITHUB_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 font-mono text-[11px] text-subtext border border-border rounded-button px-5 py-2.5 hover:text-foreground transition-colors"
      >
        Ver código en GitHub →
      </a>
    </div>
  );
}
