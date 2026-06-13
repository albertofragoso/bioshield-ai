import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import {
  useBiomarkerStatus,
  useExtractBiomarkers,
  useUploadBiomarkers,
  useDeleteBiomarkers,
  biosyncKeys,
} from "./use-biosync";
import { HttpError } from "@/lib/api/client";

vi.mock("@/lib/api/biosync", () => ({
  getBiomarkerStatus: vi.fn(),
  extractBiomarkers: vi.fn(),
  uploadBiomarkers: vi.fn(),
  deleteBiomarkers: vi.fn(),
}));

import * as biosyncApi from "@/lib/api/biosync";

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

describe("biosyncKeys", () => {
  it("returns stable query key for status", () => {
    expect(biosyncKeys.status()).toEqual(["biosync-status"]);
  });
});

describe("useBiomarkerStatus", () => {
  it("uses correct queryKey and staleTime", async () => {
    vi.mocked(biosyncApi.getBiomarkerStatus).mockResolvedValue({ has_data: false } as never);
    const queryClient = makeClient();

    const { result } = renderHook(() => useBiomarkerStatus(), {
      wrapper: makeWrapper(queryClient),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const query = queryClient.getQueryCache().find({ queryKey: biosyncKeys.status() });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((query?.options as any)?.staleTime).toBe(5 * 60 * 1000);
  });

  it("enters error state on 404 without infinite retries", async () => {
    vi.mocked(biosyncApi.getBiomarkerStatus).mockRejectedValue(new HttpError(404, "Not Found"));
    const queryClient = makeClient();

    const { result } = renderHook(() => useBiomarkerStatus(), {
      wrapper: makeWrapper(queryClient),
    });
    await waitFor(() => expect(result.current.isError).toBe(true));

    // Retry predicate is verified separately — see "retry predicate" test
    expect(vi.mocked(biosyncApi.getBiomarkerStatus).mock.calls.length).toBeLessThanOrEqual(2);
  });

  it("retry predicate allows retries for non-404 errors", async () => {
    vi.mocked(biosyncApi.getBiomarkerStatus).mockResolvedValue({ has_data: false } as never);
    const queryClient = makeClient();

    renderHook(() => useBiomarkerStatus(), { wrapper: makeWrapper(queryClient) });
    await waitFor(() =>
      expect(queryClient.getQueryCache().find({ queryKey: biosyncKeys.status() })).toBeDefined()
    );

    const query = queryClient.getQueryCache().find({ queryKey: biosyncKeys.status() });
    const retryFn = query?.options.retry as (count: number, err: unknown) => boolean;

    expect(retryFn(0, new HttpError(500, "Server Error"))).toBe(true);
    expect(retryFn(0, new HttpError(404, "Not Found"))).toBe(false);
    expect(retryFn(0, new Error("Network error"))).toBe(true);
  });
});

describe("useExtractBiomarkers", () => {
  it("calls extractBiomarkers API", async () => {
    const extractMock = vi
      .mocked(biosyncApi.extractBiomarkers)
      .mockResolvedValue({ biomarkers: [] } as never);
    const queryClient = makeClient();

    const { result } = renderHook(() => useExtractBiomarkers(), {
      wrapper: makeWrapper(queryClient),
    });
    const file = new File(["pdf"], "lab.pdf", { type: "application/pdf" });
    act(() => result.current.mutate(file));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(extractMock.mock.calls[0][0]).toEqual(file);
  });
});

describe("useUploadBiomarkers", () => {
  it("calls uploadBiomarkers API and invalidates biosync-status", async () => {
    const uploadMock = vi
      .mocked(biosyncApi.uploadBiomarkers)
      .mockResolvedValue({ has_data: true } as never);
    const queryClient = makeClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useUploadBiomarkers(), {
      wrapper: makeWrapper(queryClient),
    });
    act(() => result.current.mutate({ biomarkers: [], lab_name: null, test_date: null }));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(uploadMock.mock.calls[0][0]).toEqual({
      biomarkers: [],
      lab_name: null,
      test_date: null,
    });
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: biosyncKeys.status() })
    );
  });
});

describe("useDeleteBiomarkers", () => {
  beforeEach(() => {
    vi.mocked(biosyncApi.deleteBiomarkers).mockResolvedValue(undefined);
  });

  it("invalidates biosync-status on success", async () => {
    const queryClient = makeClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useDeleteBiomarkers(), {
      wrapper: makeWrapper(queryClient),
    });
    act(() => result.current.mutate());
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: biosyncKeys.status() })
    );
  });
});
