import type { AuthLoginResponse, AuthStatus } from "../types";
import { fetchApi } from "./client";

export function getAuthStatus(): Promise<AuthStatus> {
  return fetchApi<AuthStatus>("/auth/status");
}

export function startAuthLogin(): Promise<AuthLoginResponse> {
  return fetchApi<AuthLoginResponse>("/auth/login", { method: "POST" });
}

export function submitAuthCode(code: string): Promise<void> {
  return fetchApi<void>("/auth/callback", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export function authLogout(): Promise<void> {
  return fetchApi<void>("/auth/logout", { method: "POST" });
}
