import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { useLogin, useRegister, useLogout } from "./use-auth";

vi.mock("@/lib/api/auth", () => ({
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}));

import * as authApi from "@/lib/api/auth";

function makeWrapper(queryClient: QueryClient) {
  function Wrapper({ children }: { children: React.ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  }
  return Wrapper;
}

describe("useLogin", () => {
  it("calls login API with provided credentials", async () => {
    const loginMock = vi.mocked(authApi.login).mockResolvedValue({} as never);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });

    const { result } = renderHook(() => useLogin(), { wrapper: makeWrapper(queryClient) });

    act(() => result.current.mutate({ email: "a@b.com", password: "secret123" }));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(loginMock.mock.calls[0][0]).toEqual({ email: "a@b.com", password: "secret123" });
  });
});

describe("useRegister", () => {
  it("calls register then login with same credentials", async () => {
    const registerMock = vi.mocked(authApi.register).mockResolvedValue({} as never);
    const loginMock = vi.mocked(authApi.login).mockResolvedValue({} as never);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const callOrder: string[] = [];
    registerMock.mockImplementation(async () => {
      callOrder.push("register");
      return {} as never;
    });
    loginMock.mockImplementation(async () => {
      callOrder.push("login");
      return {} as never;
    });

    const { result } = renderHook(() => useRegister(), { wrapper: makeWrapper(queryClient) });

    act(() => result.current.mutate({ email: "a@b.com", password: "secret123" }));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(callOrder).toEqual(["register", "login"]);
    expect(registerMock).toHaveBeenCalledWith({ email: "a@b.com", password: "secret123" });
    expect(loginMock).toHaveBeenCalledWith({ email: "a@b.com", password: "secret123" });
  });
});

describe("useLogout", () => {
  beforeEach(() => {
    vi.mocked(authApi.logout).mockResolvedValue(undefined);
  });

  it("calls cancelQueries before removeQueries on success", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const callOrder: string[] = [];
    const cancelSpy = vi.spyOn(queryClient, "cancelQueries").mockImplementation(async () => {
      callOrder.push("cancel");
    });
    const removeSpy = vi.spyOn(queryClient, "removeQueries").mockImplementation(() => {
      callOrder.push("remove");
    });

    const { result } = renderHook(() => useLogout(), { wrapper: makeWrapper(queryClient) });

    act(() => result.current.mutate());
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(callOrder).toEqual(["cancel", "remove"]);
    expect(cancelSpy).toHaveBeenCalledTimes(1);
    expect(removeSpy).toHaveBeenCalledWith({ predicate: expect.any(Function) });
  });

  it("removes all queries — predicate returns true for any query", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    let capturedPredicate: ((query: unknown) => boolean) | undefined;
    vi.spyOn(queryClient, "cancelQueries").mockResolvedValue();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    vi.spyOn(queryClient, "removeQueries").mockImplementation((filters?: any) => {
      capturedPredicate = filters?.predicate;
    });

    const { result } = renderHook(() => useLogout(), { wrapper: makeWrapper(queryClient) });

    act(() => result.current.mutate());
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(capturedPredicate).toBeDefined();
    expect(capturedPredicate!({ queryKey: ["any-key"] })).toBe(true);
  });
});
