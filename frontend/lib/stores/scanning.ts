"use client";

import { create } from "zustand";

export type ScanStreamStatus = "idle" | "streaming" | "done" | "error";

export interface IngredientResult {
  name: string;
  is_concerning: boolean;
  concern_detail: string | null;
  is_conflicting: boolean;
  conflict_detail: string | null;
}

export interface PersonalizedInsight {
  insight: string;
  severity: string;
}

export interface ScanPartial {
  productName?: string;
  productBrand?: string;
  ingredients?: IngredientResult[];
  personalized_insights?: PersonalizedInsight[];
  semaphore?: string;
  conflict_severity?: string | null;
}

interface ScanStreamingState {
  scanId: string | null;
  productBarcode: string | null;
  status: ScanStreamStatus;
  partial: ScanPartial;
  _abort: AbortController | null;

  startBarcodeStream: (barcode: string) => void;
  startPhotoStream: (file: File) => void;
  clearStream: () => void;
  _handleEvent: (eventName: string, data: unknown) => void;
}

export const useScanStreamingStore = create<ScanStreamingState>((set, get) => ({
  scanId: null,
  productBarcode: null,
  status: "idle",
  partial: {},
  _abort: null,

  startBarcodeStream: (barcode) => {
    const prevAbort = get()._abort;
    prevAbort?.abort();

    const abort = new AbortController();
    set({ scanId: null, productBarcode: barcode, status: "streaming", partial: {}, _abort: abort });

    _consumeStream(
      fetch("/api/scan/barcode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ barcode }),
        credentials: "include",
        signal: abort.signal,
      }),
      get,
      set,
    );
  },

  startPhotoStream: (file) => {
    const prevAbort = get()._abort;
    prevAbort?.abort();

    const abort = new AbortController();
    const formData = new FormData();
    formData.append("file", file);

    set({ scanId: null, productBarcode: null, status: "streaming", partial: {}, _abort: abort });

    _consumeStream(
      fetch("/api/scan/photo", {
        method: "POST",
        body: formData,
        credentials: "include",
        signal: abort.signal,
      }),
      get,
      set,
    );
  },

  clearStream: () => {
    get()._abort?.abort();
    set({ scanId: null, productBarcode: null, status: "idle", partial: {}, _abort: null });
  },

  _handleEvent: (eventName, data) => {
    const d = data as Record<string, unknown>;
    switch (eventName) {
      case "init":
        set({ scanId: String(d.scan_id), productBarcode: String(d.product_barcode) });
        break;
      case "ingredients":
        set((s) => ({
          partial: {
            ...s.partial,
            productName: d.product_name as string | undefined,
            productBrand: d.product_brand as string | undefined,
            ingredients: d.ingredients as IngredientResult[],
          },
        }));
        break;
      case "insights":
        set((s) => ({
          partial: {
            ...s.partial,
            personalized_insights: d.personalized_insights as PersonalizedInsight[],
          },
        }));
        break;
      case "semaphore":
        set((s) => ({
          partial: {
            ...s.partial,
            semaphore: d.semaphore as string,
            conflict_severity: d.conflict_severity as string | null,
            // preferir ingredientes actualizados del evento si vienen
            ingredients: (d.ingredients as IngredientResult[]) ?? s.partial.ingredients,
          },
        }));
        break;
      case "done":
        set({ status: "done" });
        break;
      case "error":
        set({ status: "error" });
        break;
    }
  },
}));

// Consume el stream SSE fuera del store para no bloquear el thread de Zustand
async function _consumeStream(
  fetchPromise: Promise<Response>,
  get: () => ScanStreamingState,
  set: (partial: Partial<ScanStreamingState> | ((s: ScanStreamingState) => Partial<ScanStreamingState>)) => void,
) {
  try {
    const response = await fetchPromise;
    if (!response.ok || !response.body) {
      set({ status: "error" });
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let currentEvent = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (line.startsWith("event:")) {
          currentEvent = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          const rawData = line.slice(5).trim();
          try {
            const parsed = JSON.parse(rawData);
            get()._handleEvent(currentEvent, parsed);
          } catch {
            // línea de datos malformada — ignorar
          }
          currentEvent = "";
        }
      }
    }
  } catch (err) {
    if ((err as Error).name !== "AbortError") {
      set({ status: "error" });
    }
  }
}
