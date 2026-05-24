/**
 * Feature flags for granular rollout control of landing page redesign features.
 * If Lighthouse gates fail, individual features can be disabled without full rollback.
 */

// Mascot Guide section + interactions (animated guide card)
export const FF_MASCOT_GUIDE = process.env.NEXT_PUBLIC_FF_MASCOT_GUIDE !== "false";

// Risk Pills visualization (ingredient risk color indicators)
export const FF_RISK_PILLS = process.env.NEXT_PUBLIC_FF_RISK_PILLS !== "false";
