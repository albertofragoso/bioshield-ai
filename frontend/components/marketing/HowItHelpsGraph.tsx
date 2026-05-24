"use client";

import { useEffect, useRef, useState } from "react";
import { MascotGuide } from "@/components/marketing/MascotGuide";
import { FF_MASCOT_GUIDE } from "@/lib/featureFlags";

const PIPELINE_STEPS = [
  { num: "01", icon: "📷", label: "Escanear barcode" },
  { num: "02", icon: "🔍", label: "Identificar producto" },
  { num: "03", icon: "🧬", label: "Extraer ingredientes" },
  { num: "04", icon: "🔗", label: "Cruzar biomarkers" },
  { num: "05", icon: "🚨", label: "Alertar riesgos" },
];

export function HowItHelpsGraph() {
  const [activeStep, setActiveStep] = useState(-1);
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;

    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        observer.disconnect();

        if (prefersReduced) {
          setActiveStep(PIPELINE_STEPS.length - 1);
          return;
        }

        let step = 0;
        setActiveStep(0);
        const interval = setInterval(() => {
          step += 1;
          if (step >= PIPELINE_STEPS.length) {
            clearInterval(interval);
            return;
          }
          setActiveStep(step);
        }, 600);
      },
      { threshold: 0.1, rootMargin: "0px 0px -50px 0px" }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-6">
      {FF_MASCOT_GUIDE && (
        <div className="flex justify-center mb-8">
          <MascotGuide
            src="/avatars/welcome.png"
            alt="BioShield mascota explicando el pipeline"
            speech="Así es como analizo cada producto en segundos…"
            size="md"
          />
        </div>
      )}

      <h2 className="font-sans text-3xl lg:text-4xl font-bold text-center text-foreground mb-16">
        Cómo te ayuda BioShield
      </h2>

      <div
        ref={sectionRef}
        className="flex flex-col lg:flex-row items-center lg:items-start justify-center gap-0"
      >
        {PIPELINE_STEPS.map((step, idx) => {
          const isDone = idx < activeStep;
          const isActive = idx === activeStep;
          const isPending = idx > activeStep;

          const iconBoxClass = isActive
            ? "bg-gradient-to-br from-teal-500 to-sky-500 shadow-[0_0_16px_rgba(13,148,136,0.5)]"
            : isDone
              ? "bg-[#0d2e2e] border border-teal-700"
              : "bg-[#111] border border-[#1a1a2e]";

          const labelClass = isActive
            ? "text-white font-semibold"
            : isDone
              ? "text-teal-400 font-medium"
              : "text-gray-600 font-normal";

          const numClass = isActive || isDone ? "text-teal-400" : "text-gray-700";

          const lineActive = isDone || isActive;

          return (
            <div key={step.num} className="flex flex-row lg:flex-col items-center flex-1">
              {/* Step node */}
              <div className="flex flex-col items-center">
                {/* Step number */}
                <span
                  className={`font-mono text-xs mb-2 transition-colors duration-300 ${numClass}`}
                >
                  {step.num}
                </span>

                {/* Icon box */}
                <div
                  className={`w-9 h-9 rounded-lg flex items-center justify-center text-lg transition-all duration-500 ${iconBoxClass}`}
                >
                  {step.icon}
                </div>

                {/* Label */}
                <span
                  className={`mt-2 text-center text-xs transition-colors duration-300 ${labelClass} ${isPending ? "opacity-40" : "opacity-100"}`}
                  style={{ maxWidth: "80px" }}
                >
                  {step.label}
                </span>
              </div>

              {/* Connecting line (after each step except last) */}
              {idx < PIPELINE_STEPS.length - 1 && (
                <div
                  className={`
                    hidden lg:block h-[2px] flex-1 mx-2 mt-[18px] self-start transition-colors duration-500
                    ${lineActive ? "bg-teal-600" : "bg-[#1a1a2e]"}
                  `}
                  aria-hidden="true"
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
