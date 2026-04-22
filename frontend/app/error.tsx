"use client";

import { ErrorPage } from "@/components/ErrorPage";

export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return <ErrorPage onRetry={reset} />;
}
