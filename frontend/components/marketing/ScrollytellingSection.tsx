"use client";

import { useEffect, useRef, useState } from "react";
import { StaticBeats, BEATS } from "./StaticBeats";
import { ScrollyBeat } from "./ScrollyBeat";
import { NutritionLabelPanel } from "./NutritionLabelPanel";

export function ScrollytellingSection() {
  const [isStaticMode, setIsStaticMode] = useState(true); // default true (SSR safe)
  const sectionRef = useRef<HTMLElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const isMobile = window.innerWidth < 1024;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- valid SSR-safe init: reads window only after mount
    setIsStaticMode(prefersReduced || isMobile);
  }, []);

  useEffect(() => {
    if (isStaticMode) return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let ctx: any;
    let cancelled = false;

    const init = async () => {
      const { gsap } = await import("gsap");
      const { ScrollTrigger } = await import("gsap/ScrollTrigger");
      if (cancelled) return;
      gsap.registerPlugin(ScrollTrigger);

      ctx = gsap.context(() => {
        // Pin full grid for entire 300vh scroll.
        ScrollTrigger.create({
          trigger: sectionRef.current,
          start: "top top",
          end: "bottom top",
          pin: panelRef.current,
          pinSpacing: false,
        });

        // Smooth exit: fade the full grid over the last 10% of scroll so the
        // transition into the next section is gradual rather than a hard cut.
        // Scrub handles both forward and backward directions automatically.
        gsap
          .timeline({
            scrollTrigger: {
              trigger: sectionRef.current,
              start: "90% top",
              end: "bottom top",
              scrub: 1,
            },
          })
          .to(panelRef.current, { autoAlpha: 0, ease: "power1.in" });

        // Beat 1 → Beat 2 (25–50%)
        const tl2 = gsap.timeline({
          scrollTrigger: {
            trigger: sectionRef.current,
            start: "25% top",
            end: "50% top",
            scrub: 1,
          },
        });
        tl2
          .to(".label-clean", { opacity: 0, duration: 0.3 })
          .fromTo(".label-additives", { opacity: 0 }, { opacity: 1, duration: 0.3 }, "<")
          .fromTo(
            ".pill-e407, .pill-e621, .pill-e202",
            { y: 20, opacity: 0 },
            { y: 0, opacity: 1, stagger: 0.1 }
          );

        // Beat 2 → Beat 3 (50–75%)
        const tl3 = gsap.timeline({
          scrollTrigger: {
            trigger: sectionRef.current,
            start: "50% top",
            end: "75% top",
            scrub: 1,
          },
        });
        tl3
          .to(".label-additives", { opacity: 0.4, duration: 0.3 })
          .fromTo(".blood-overlay", { opacity: 0 }, { opacity: 1, duration: 0.5 }, "<");

        // Beat 3 → Beat 4 (75–90%): ends before exit fade so verdict card
        // is fully visible at 1.0 opacity before the panel starts fading out.
        const tl4 = gsap.timeline({
          scrollTrigger: {
            trigger: sectionRef.current,
            start: "75% top",
            end: "90% top",
            scrub: 1,
          },
        });
        tl4
          .to(".blood-overlay", { opacity: 0, duration: 0.3 })
          .fromTo(
            ".verdict-card",
            { opacity: 0, scale: 0.95 },
            { opacity: 1, scale: 1, duration: 0.4 },
            "<"
          );

        // Beat text fade-ins per scroll zone
        const starts = ["top top", "25% top", "50% top", "75% top"];
        const ends = ["25% top", "50% top", "75% top", "90% top"];
        BEATS.forEach((_, i) => {
          gsap.fromTo(
            `.scroll-beat-${i}`,
            { opacity: i === 0 ? 1 : 0.2 },
            {
              opacity: 1,
              scrollTrigger: {
                trigger: sectionRef.current,
                start: starts[i],
                end: ends[i],
                scrub: 1,
              },
            }
          );
        });
      }, sectionRef);
    };

    init();

    return () => {
      cancelled = true;
      ctx?.revert();
    };
  }, [isStaticMode]);

  if (isStaticMode) {
    return <StaticBeats />;
  }

  return (
    <section
      ref={sectionRef}
      className="relative lg:h-[300vh] h-auto"
      style={{ backgroundColor: "#080C07" }}
      aria-label="Cómo BioShield analiza tu alimento"
    >
      {/* panelRef wraps the full grid — GSAP pins both columns together.
          Background required: when position:fixed (during pin), the panel floats
          over content below; without it, subsequent sections show through. */}
      <div
        ref={panelRef}
        className="lg:h-screen flex items-center w-full z-10"
        style={{ backgroundColor: "#080C07" }}
      >
        <div className="grid lg:grid-cols-2 w-full h-full">
          {/* Left: nutrition label panel */}
          <div className="relative h-screen">
            <NutritionLabelPanel />
          </div>

          {/* Right: scroll beats column */}
          <div className="flex flex-col justify-around h-screen px-8 lg:px-16 py-16">
            {BEATS.map((beat, i) => (
              <ScrollyBeat key={i} beat={beat} beatIndex={i} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
