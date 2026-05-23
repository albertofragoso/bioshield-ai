import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

const FAQ_ITEMS = [
  {
    q: "¿BioShield diagnostica enfermedades?",
    a: "No. Es una herramienta educativa e informativa. Las decisiones de salud son entre vos y tu médico. BioShield te muestra correlaciones reportadas en bases de datos públicas, no diagnósticos clínicos.",
  },
  {
    q: "¿Está avalada por COFEPRIS o FDA?",
    a: "No. La información proviene de bases de datos regulatorias públicas (FDA EAFUS, EFSA OpenFoodTox, Codex Alimentarius), pero BioShield AI no es un producto médico ni está sujeto a aval regulatorio de salud.",
  },
  {
    q: "¿Qué hace con mis biomarcadores de laboratorio?",
    a: "Los cifra con AES-256 antes de almacenarlos. Expiran automáticamente a los 180 días. Puedes borrarlos en cualquier momento desde la app, o solicitar eliminación de cuenta a privacy@bioshield.mx.",
  },
  {
    q: "¿Cuánto va a costar?",
    a: "El núcleo de BioShield será gratuito siempre. Estamos evaluando un tier Pro para usuarios intensivos. Por ahora solo estamos en lista de espera.",
  },
  {
    q: "¿Cuándo lanza?",
    a: "Beta limitada en Q2 2026. Si te anotas en la lista, serás de los primeros en recibir acceso.",
  },
  {
    q: "¿En qué países funciona?",
    a: "México primero. Después LatAm. El catálogo de productos de Open Food Facts ya tiene cobertura amplia en MX.",
  },
  {
    q: "¿Funciona sin conexión?",
    a: "No por ahora. El análisis requiere conexión para consultar las bases regulatorias y el modelo de IA.",
  },
  {
    q: "¿Puedo contribuir productos?",
    a: "Sí. BioShield está integrado con Open Food Facts. Podés contribuir fotos y datos de productos directamente desde la app.",
  },
  {
    q: "¿Hay app móvil?",
    a: "Es una PWA (Progressive Web App) optimizada para móvil. Funciona desde el navegador sin instalar nada, y podés agregarla a tu pantalla de inicio.",
  },
  {
    q: "¿Cómo borro mis datos?",
    a: "En la sección Biosync de la app hay un botón 'Borrar todo' para eliminar tus biomarcadores. Para eliminar tu cuenta completa, escribí a privacy@bioshield.mx.",
  },
];

export function MarketingFAQ() {
  return (
    <div className="max-w-2xl mx-auto px-6">
      <h2 className="font-sans text-3xl font-bold text-center text-foreground mb-12">
        Preguntas frecuentes
      </h2>

      <Accordion type="single" collapsible className="space-y-2">
        {FAQ_ITEMS.map((item, idx) => (
          <AccordionItem
            key={idx}
            value={`item-${idx}`}
            className="border border-border rounded-card px-4 overflow-hidden"
            style={{ background: "var(--surface)" }}
          >
            <AccordionTrigger className="font-sans text-sm text-foreground text-left hover:no-underline py-4">
              {item.q}
            </AccordionTrigger>
            <AccordionContent className="font-mono text-[11px] text-subtext pb-4 leading-relaxed">
              {item.a}
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </div>
  );
}
