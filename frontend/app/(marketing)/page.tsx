import { HeroWaitlistCTA } from "@/components/marketing/HeroWaitlistCTA";
import { MascotGuide } from "@/components/marketing/MascotGuide";
import { HeroCursorGlow } from "@/components/marketing/HeroCursorGlow";
import { HeroFloatingBadges } from "@/components/marketing/HeroFloatingBadges";
import { PipelineLoopAnim } from "@/components/marketing/PipelineLoopAnim";
import { FF_MASCOT_GUIDE } from "@/lib/featureFlags";
import { RevealMomentStory } from "@/components/marketing/RevealMomentStory";
import { HowItHelpsGraph } from "@/components/marketing/HowItHelpsGraph";
import { BiomarkerSplitPanel } from "@/components/marketing/BiomarkerSplitPanel";
import { RegulatoryTrust } from "@/components/marketing/RegulatoryTrust";
import { WaitlistHero } from "@/components/marketing/WaitlistHero";
import { MarketingFAQ } from "@/components/marketing/MarketingFAQ";
import { StackStrip } from "@/components/marketing/StackStrip";
import { MarketingFooter } from "@/components/marketing/MarketingFooter";

export const dynamic = "force-static";

export default function LandingPage() {
  return (
    <>
      {/* Sección 1: Hero */}
      <section
        id="hero"
        className="relative min-h-screen flex flex-col items-center justify-center px-6 py-24 overflow-hidden"
        style={{
          backgroundImage: "radial-gradient(rgba(13,148,136,0.10) 1px, transparent 1px)",
          backgroundSize: "28px 28px",
        }}
      >
        {/* Cursor-following ambient glow — client component */}
        <HeroCursorGlow />

        <div className="relative z-10 flex flex-col lg:flex-row items-center gap-12 lg:gap-16 max-w-5xl w-full">
          {/* Left: copy + CTA */}
          <div className="flex-1 text-center lg:text-left">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-brand-green mb-4 opacity-80">
              BioShield AI · Nutrición inteligente
            </p>

            <h1 className="font-sans text-4xl lg:text-5xl font-bold text-foreground leading-tight mb-5">
              Lo que comes,{" "}
              <span
                className="text-brand-green"
                style={{ textShadow: "0 0 30px rgba(74,222,128,.4)" }}
              >
                en términos de TU sangre.
              </span>
            </h1>

            <p className="text-subtext text-base lg:text-lg leading-relaxed mb-8 max-w-lg mx-auto lg:mx-0">
              Escanea cualquier producto. Descubre qué aditivos contiene y si son compatibles con
              tus análisis de laboratorio.
            </p>

            <div className="flex flex-col sm:flex-row items-center lg:items-start gap-4 mb-6">
              <HeroWaitlistCTA />
            </div>

            <a
              href="#reveal"
              className="font-mono text-[11px] text-subtext hover:text-brand-green transition-colors uppercase tracking-[0.06em]"
            >
              Ver cómo funciona ↓
            </a>

            <p className="mt-6 font-mono text-[9px] text-subtext opacity-50 tracking-[0.12em] uppercase">
              hack your nutrition · protect your biology
            </p>
          </div>

          {/* Right: mascot (with floating badges) + pipeline demo */}
          <div id="demo" className="flex-1 flex flex-col items-center gap-8 w-full">
            {FF_MASCOT_GUIDE && (
              <div className="relative">
                <HeroFloatingBadges />
                <MascotGuide src="/avatars/main.png" alt="BioShield mascot" speech="" size="lg" />
              </div>
            )}
            <PipelineLoopAnim />
          </div>
        </div>
      </section>

      {/* Sección 2: El momento revelador */}
      <section id="reveal" className="py-24" style={{ background: "var(--surface)" }}>
        <RevealMomentStory />
      </section>

      {/* Sección 3: Cómo te ayuda */}
      <section id="how" className="py-24 bg-background">
        <HowItHelpsGraph />
      </section>

      {/* Sección 4: Por qué BioShield */}
      <section id="why" className="py-24" style={{ background: "var(--surface)" }}>
        <BiomarkerSplitPanel />
      </section>

      {/* Sección 5: Confianza regulatoria */}
      <section id="trust" className="py-20 bg-background">
        <RegulatoryTrust />
      </section>

      {/* Sección 6: Waitlist CTA completo */}
      <section id="waitlist" className="py-24" style={{ background: "var(--surface)" }}>
        <WaitlistHero />
      </section>

      {/* Sección 7: FAQ */}
      <section id="faq" className="py-24 bg-background">
        <MarketingFAQ />
      </section>

      {/* Sección 8: Stack técnico */}
      <section id="stack" className="py-20" style={{ background: "var(--surface)" }}>
        <StackStrip />
      </section>

      {/* Sección 9: Footer */}
      <MarketingFooter />
    </>
  );
}
