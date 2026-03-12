import type { AuthLoginResponse, AuthStatus } from "../types";
import { fetchApi } from "./client";

// ── User auth ──

export interface RegisterData {
  email: string;
  password: string;
  name: string;
}

export interface LoginData {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    name: string;
    role: string;
    created_at: string;
  };
}

export function register(data: RegisterData): Promise<TokenResponse> {
  return fetchApi<TokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function login(data: LoginData): Promise<TokenResponse> {
  return fetchApi<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getMe(): Promise<TokenResponse["user"]> {
  return fetchApi<TokenResponse["user"]>("/auth/me");
}

// ── Claude OAuth ──

export function getAuthStatus(): Promise<AuthStatus> {
  return fetchApi<AuthStatus>("/auth/claude/status");
}

export function startAuthLogin(): Promise<AuthLoginResponse> {
  return fetchApi<AuthLoginResponse>("/auth/claude/login", { method: "POST" });
}

export function submitAuthCode(code: string): Promise<void> {
  return fetchApi<void>("/auth/claude/callback", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export function authLogout(): Promise<void> {
  return fetchApi<void>("/auth/claude/logout", { method: "POST" });
}
