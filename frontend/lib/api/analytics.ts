import { apiFetch } from "./client";
import type { AnalyticsEventIn } from "./types";

export async function recordAnalyticsEvent(body: AnalyticsEventIn): Promise<void> {
  try {
    await apiFetch<void>("/analytics/event", {
      method: "POST",
      body: JSON.stringify(body),
    });
  } catch {
    // fire-and-forget — never throw
  }
}
