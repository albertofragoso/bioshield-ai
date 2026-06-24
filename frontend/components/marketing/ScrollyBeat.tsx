import { BEATS } from "./StaticBeats";

interface ScrollyBeatProps {
  beat: (typeof BEATS)[number];
  beatIndex: number;
  isActive?: boolean;
}

export function ScrollyBeat({ beat, beatIndex, isActive }: ScrollyBeatProps) {
  const hasPills = "pills" in beat && beat.pills;
  const hasDisclaimer = "disclaimer" in beat && beat.disclaimer;
  const hasCta = "cta" in beat && beat.cta;

  return (
    <div
      className={`scroll-beat-${beatIndex} flex flex-col gap-3`}
      style={{ opacity: isActive ? 1 : undefined }}
    >
      {/* Headline */}
      <h3
        className="font-semibold text-xl leading-snug"
        style={{ color: beat.accentColor, fontFamily: "Space Grotesk, sans-serif" }}
      >
        {beat.headline}
      </h3>

      {/* Body */}
      <p
        className="text-sm leading-relaxed max-w-sm"
        style={{ color: "#A8C5A8", fontFamily: "Space Grotesk, sans-serif" }}
      >
        {beat.body}
      </p>

      {/* Pills */}
      {hasPills && (
        <div className="flex flex-wrap gap-2">
          {(beat as { pills: readonly string[] }).pills.map((pill) => (
            <span
              key={pill}
              className="px-3 py-1 rounded-full text-xs font-medium"
              style={{
                backgroundColor: "#F59E0B22",
                color: "#F59E0B",
                fontFamily: "JetBrains Mono, monospace",
                border: "1px solid #F59E0B44",
              }}
            >
              {pill}
            </span>
          ))}
        </div>
      )}

      {/* Disclaimer */}
      {hasDisclaimer && (
        <p
          className="text-xs"
          style={{ color: "#6B8A6A", fontFamily: "Space Grotesk, sans-serif" }}
        >
          {(beat as { disclaimer: string }).disclaimer}
        </p>
      )}

      {/* CTA */}
      {hasCta && (
        <a
          href="#waitlist"
          className="inline-block mt-2 px-6 py-3 rounded-xl text-sm font-semibold transition-opacity hover:opacity-90 w-fit"
          style={{
            backgroundColor: "#4ADE80",
            color: "#080C07",
            fontFamily: "Space Grotesk, sans-serif",
          }}
        >
          Únete a la lista de espera →
        </a>
      )}
    </div>
  );
}
