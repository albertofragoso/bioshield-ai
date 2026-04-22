import { apiFetch, HttpError } from "./client";
import type { LoginRequest, RegisterRequest, TokenResponse, UserResponse, ApiError } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Login usa fetch directo para que un 401 de credenciales incorrectas
// no dispare el interceptor de refresh de apiFetch.
export async function login(body: LoginRequest): Promise<TokenResponse> {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({} as ApiError));
    throw new HttpError(res.status, payload.detail ?? res.statusText);
  }
  return res.json() as Promise<TokenResponse>;
}

export async function register(body: RegisterRequest): Promise<UserResponse> {
  return apiFetch<UserResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function logout(): Promise<void> {
  return apiFetch<void>("/auth/logout", { method: "POST" });
}

export async function refresh(): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/refresh", { method: "POST" });
}
