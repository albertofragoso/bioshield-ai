import { describe, it, expect, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import {
  useScanResult,
  useScanHistory,
  useAlternatives,
  useSharedScan,
  useLinkPhotoToBarcode,
  useCreateShareLink,
  useRevokeShareLink,
  useContributeToOff,
  scanKeys,
} from "./use-scan";

vi.mock("@/lib/api/scan", () => ({
  getScanResult: vi.fn(),
  getScanHistory: vi.fn(),
  getAlternatives: vi.fn(),
  getSharedScan: vi.fn(),
  linkPhotoToBarcode: vi.fn(),
  createShareLink: vi.fn(),
  revokeShareLink: vi.fn(),
  contributeToOff: vi.fn(),
}));

import * as scanApi from "@/lib/api/scan";

function makeWrapper(queryClient: QueryClient) {
  function Wrapper({ children }: { children: React.ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  }
  return Wrapper;
}

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false, networkMode: "always" },
      mutations: { retry: false, networkMode: "always" },
    },
  });
}

describe("scanKeys", () => {
  it("generates stable keys", () => {
    expect(scanKeys.result("abc123")).toEqual(["scan", "abc123"]);
    expect(scanKeys.history(10)).toEqual(["scan-history", 10]);
    expect(scanKeys.alternatives("7501030")).toEqual(["alternatives", "7501030"]);
    expect(scanKeys.shared("tok123")).toEqual(["shared-scan", "tok123"]);
  });
});

describe("useScanResult", () => {
  it("fetches scan by id with staleTime Infinity", async () => {
    vi.mocked(scanApi.getScanResult).mockResolvedValue({ product_barcode: "abc" } as never);
    const queryClient = makeClient();

    const { result } = renderHook(() => useScanResult("abc"), {
      wrapper: makeWrapper(queryClient),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const query = queryClient.getQueryCache().find({ queryKey: scanKeys.result("abc") });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((query?.options as any)?.staleTime).toBe(Infinity);
    expect(scanApi.getScanResult).toHaveBeenCalledWith("abc");
  });

  it("is disabled when id is empty", () => {
    const queryClient = makeClient();
    const { result } = renderHook(() => useScanResult(""), { wrapper: makeWrapper(queryClient) });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("accepts enabled override", () => {
    vi.mocked(scanApi.getScanResult).mockResolvedValue({} as never);
    const queryClient = makeClient();
    const { result } = renderHook(() => useScanResult("abc", { enabled: false }), {
      wrapper: makeWrapper(queryClient),
    });
    expect(result.current.fetchStatus).toBe("idle");
  });
});

describe("useScanHistory", () => {
  it("fetches history with limit and staleTime 60s", async () => {
    vi.mocked(scanApi.getScanHistory).mockResolvedValue([]);
    const queryClient = makeClient();

    const { result } = renderHook(() => useScanHistory(5), { wrapper: makeWrapper(queryClient) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(scanApi.getScanHistory).toHaveBeenCalledWith(5);
    const query = queryClient.getQueryCache().find({ queryKey: scanKeys.history(5) });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((query?.options as any)?.staleTime).toBe(60 * 1000);
  });

  it("defaults to limit 10", async () => {
    vi.mocked(scanApi.getScanHistory).mockResolvedValue([]);
    const queryClient = makeClient();

    renderHook(() => useScanHistory(), { wrapper: makeWrapper(queryClient) });
    await waitFor(() => expect(vi.mocked(scanApi.getScanHistory)).toHaveBeenCalledWith(10));
  });
});

describe("useAlternatives", () => {
  it("is disabled when barcode is undefined", () => {
    const queryClient = makeClient();
    const { result } = renderHook(() => useAlternatives(undefined), {
      wrapper: makeWrapper(queryClient),
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("fetches when barcode is provided", async () => {
    vi.mocked(scanApi.getAlternatives).mockResolvedValue({ alternatives: [] } as never);
    const queryClient = makeClient();

    const { result } = renderHook(() => useAlternatives("7501030"), {
      wrapper: makeWrapper(queryClient),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(scanApi.getAlternatives).toHaveBeenCalledWith("7501030");
  });
});

describe("useLinkPhotoToBarcode", () => {
  it("calls linkPhotoToBarcode with pseudoBarcode and barcode", async () => {
    const mock = vi
      .mocked(scanApi.linkPhotoToBarcode)
      .mockResolvedValue({ product_barcode: "real123" } as never);
    const queryClient = makeClient();

    const { result } = renderHook(() => useLinkPhotoToBarcode(), {
      wrapper: makeWrapper(queryClient),
    });
    act(() => result.current.mutate({ pseudoBarcode: "pseudo", barcode: "real123" }));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mock).toHaveBeenCalledWith("pseudo", "real123");
  });
});

describe("useCreateShareLink", () => {
  it("calls createShareLink with scanDbId", async () => {
    const mock = vi
      .mocked(scanApi.createShareLink)
      .mockResolvedValue({ share_url: "http://x", expires_at: "" });
    const queryClient = makeClient();

    const { result } = renderHook(() => useCreateShareLink(), {
      wrapper: makeWrapper(queryClient),
    });
    act(() => result.current.mutate("scan-id-1"));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mock.mock.calls[0][0]).toBe("scan-id-1");
  });
});

describe("useRevokeShareLink", () => {
  it("calls revokeShareLink with scanDbId", async () => {
    const mock = vi.mocked(scanApi.revokeShareLink).mockResolvedValue(undefined);
    const queryClient = makeClient();

    const { result } = renderHook(() => useRevokeShareLink(), {
      wrapper: makeWrapper(queryClient),
    });
    act(() => result.current.mutate("scan-id-1"));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mock.mock.calls[0][0]).toBe("scan-id-1");
  });
});

describe("useContributeToOff", () => {
  it("calls contributeToOff with request body", async () => {
    const mock = vi.mocked(scanApi.contributeToOff).mockResolvedValue({ success: true } as never);
    const queryClient = makeClient();

    const payload = { barcode: "1234", ingredients: ["sal"], consent: true as const };
    const { result } = renderHook(() => useContributeToOff(), {
      wrapper: makeWrapper(queryClient),
    });
    act(() => result.current.mutate(payload));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mock.mock.calls[0][0]).toEqual(payload);
  });
});

describe("useSharedScan", () => {
  it("fetches shared scan by token", async () => {
    vi.mocked(scanApi.getSharedScan).mockResolvedValue({ product_barcode: "abc" } as never);
    const queryClient = makeClient();

    const { result } = renderHook(() => useSharedScan("tok123"), {
      wrapper: makeWrapper(queryClient),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(scanApi.getSharedScan).toHaveBeenCalledWith("tok123");
  });
});
