import { AILoadingState, SCAN_PHASES } from "@/components/AILoadingState";

export function PhotoLoadingState() {
  return <AILoadingState phases={SCAN_PHASES} />;
}
