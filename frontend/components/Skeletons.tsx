import { cn } from "@/lib/utils";

const shimmerStyle = {
  background: "linear-gradient(90deg, rgba(74,222,128,.06) 25%, rgba(74,222,128,.1) 50%, rgba(74,222,128,.06) 75%)",
  backgroundSize: "200% 100%",
  animation: "shimmer 1.5s infinite",
} as const;

function SkeletonBase({ className }: { className?: string }) {
  return (
    <div
      className={cn("rounded-input", className)}
      style={shimmerStyle}
      aria-hidden
    />
  );
}

// Placeholder de card grande (hero, biosync status, etc.)
export function SkeletonCard() {
  return (
    <div className="bs-card p-6 flex flex-col gap-4" aria-hidden>
      <SkeletonBase className="h-6 w-2/3" />
      <SkeletonBase className="h-4 w-full" />
      <SkeletonBase className="h-4 w-4/5" />
      <SkeletonBase className="h-10 w-full mt-2" />
    </div>
  );
}

// Placeholder de fila de lista (historial, ingredientes, etc.)
export function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 py-3" aria-hidden>
      <SkeletonBase className="h-10 w-10 rounded-full shrink-0" />
      <div className="flex-1 flex flex-col gap-2">
        <SkeletonBase className="h-3.5 w-1/2" />
        <SkeletonBase className="h-3 w-1/3" />
      </div>
      <SkeletonBase className="h-4 w-4 rounded-sm shrink-0" />
    </div>
  );
}

// Placeholder del hero del semáforo (/scan/[id])
export function SkeletonHero() {
  return (
    <div className="bs-card p-6 flex flex-col sm:flex-row items-center gap-6" aria-hidden>
      <SkeletonBase className="h-[120px] w-[120px] rounded-full shrink-0" />
      <div className="flex-1 flex flex-col gap-3 w-full">
        <SkeletonBase className="h-8 w-1/2" />
        <SkeletonBase className="h-4 w-3/4" />
        <SkeletonBase className="h-4 w-2/3" />
      </div>
    </div>
  );
}
