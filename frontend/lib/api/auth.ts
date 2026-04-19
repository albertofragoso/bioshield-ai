import { apiFetch } from "./client";
import type { LoginRequest, RegisterRequest, TokenResponse, UserResponse } from "./types";

export async function login(body: LoginRequest): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  });
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
