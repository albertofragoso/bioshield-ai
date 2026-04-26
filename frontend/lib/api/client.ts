"use client";

import type { ApiError } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

let isRefreshing = false;
let refreshQueue: Array<(ok: boolean) => void> = [];

async function doRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    return res.ok;
  } catch {
    return false;
  }
}

async function waitForRefresh(): Promise<boolean> {
  return new Promise((resolve) => {
    refreshQueue.push(resolve);
  });
}

function flushRefreshQueue(ok: boolean) {
  refreshQueue.forEach((resolve) => resolve(ok));
  refreshQueue = [];
}

export class HttpError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
  }
}

async function parseError(res: Response): Promise<HttpError> {
  try {
    const body = (await res.json()) as ApiError;
    return new HttpError(res.status, body.detail ?? res.statusText);
  } catch {
    return new HttpError(res.status, res.statusText);
  }
}

type RequestOptions = RequestInit & { _retry?: boolean };

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      // Skip Content-Type for FormData — browser sets it with the correct multipart boundary
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(options.headers ?? {}),
    },
  });

  if (res.status === 401 && !options._retry) {
    if (isRefreshing) {
      const ok = await waitForRefresh();
      if (!ok) {
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("session-expired"));
        }
        throw new HttpError(401, "Session expired");
      }
      return apiFetch<T>(path, { ...options, _retry: true });
    }

    isRefreshing = true;
    const ok = await doRefresh();
    isRefreshing = false;
    flushRefreshQueue(ok);

    if (!ok) {
      // Emite evento para que el layout muestre SessionExpiredDialog en lugar de redirigir abruptamente
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("session-expired"));
      }
      throw new HttpError(401, "Session expired");
    }
    return apiFetch<T>(path, { ...options, _retry: true });
  }

  if (!res.ok) {
    throw await parseError(res);
  }

  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}
