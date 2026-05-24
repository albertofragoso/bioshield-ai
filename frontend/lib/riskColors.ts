/**
 * Single source of truth for ingredient risk color mapping.
 * Derived from fixture semaphore values (ORANGE, YELLOW, BLUE).
 * Used by MascotGuide, PipelineLoopAnim, and ingredient risk visualization components.
 */

export type RiskLevel = "ORANGE" | "YELLOW" | "BLUE";

export interface RiskStyle {
  text: string;
  bg: string;
  border: string;
  icon: string;
  ariaLabel: string;
}

/**
 * Risk color palette with semantic meanings:
 * - ORANGE: high danger (red tones, alert icon)
 * - YELLOW: moderate warning (amber tones, caution icon)
 * - BLUE: safe / no conflict detected (teal tones, checkmark icon)
 */
export const RISK_STYLES: Record<RiskLevel, RiskStyle> = {
  ORANGE: {
    text: "#f87171",
    bg: "#2d0f0f",
    border: "#4a1010",
    icon: "🚨",
    ariaLabel: "riesgo alto",
  },
  YELLOW: {
    text: "#f59e0b",
    bg: "#2d1f00",
    border: "#4a3000",
    icon: "⚠️",
    ariaLabel: "riesgo moderado",
  },
  BLUE: {
    text: "#0d9488",
    bg: "#0d2e2e",
    border: "#0d4a3a",
    icon: "✓",
    ariaLabel: "sin riesgo",
  },
};

/**
 * Determine risk level for an ingredient by checking against conflicts array.
 * Uses case-insensitive substring matching.
 *
 * @param ingredientName - Name of the ingredient to check
 * @param conflicts - Array of { ingredient: string; severity: string } from fixture
 * @returns RiskLevel: ORANGE, YELLOW, or BLUE (default if no match)
 */
export function getIngredientRisk(
  ingredientName: string,
  conflicts: Array<{ ingredient: string; severity: string }>
): RiskLevel {
  const lowerName = ingredientName.toLowerCase();

  for (const conflict of conflicts) {
    const lowerConflict = conflict.ingredient.toLowerCase();

    // Case-insensitive substring match
    if (lowerConflict.includes(lowerName) || lowerName.includes(lowerConflict)) {
      const severity = conflict.severity.toUpperCase();
      if (severity === "ORANGE" || severity === "HIGH") {
        return "ORANGE";
      }
      if (severity === "YELLOW" || severity === "MODERATE") {
        return "YELLOW";
      }
    }
  }

  // No conflict found
  return "BLUE";
}
