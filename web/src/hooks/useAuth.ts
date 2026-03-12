import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  authLogout,
  getAuthStatus,
  getMe,
  login,
  register,
  startAuthLogin,
  submitAuthCode,
} from "../api/auth";
import type { LoginData, RegisterData } from "../api/auth";
import { clearToken, setToken } from "../api/client";

const AUTH_KEY = ["auth", "status"] as const;
const USER_KEY = ["auth", "me"] as const;

// ── User auth ──

export function useCurrentUser() {
  return useQuery({
    queryKey: USER_KEY,
    queryFn: getMe,
    retry: false,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: LoginData) => login(data),
    onSuccess: (res) => {
      setToken(res.access_token);
      void queryClient.invalidateQueries({ queryKey: USER_KEY });
    },
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: RegisterData) => register(data),
    onSuccess: (res) => {
      setToken(res.access_token);
      void queryClient.invalidateQueries({ queryKey: USER_KEY });
    },
  });
}

export function useUserLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => { clearToken(); },
    onSuccess: () => {
      void queryClient.invalidateQueries();
      window.location.href = "/login";
    },
  });
}

// ── Claude OAuth ──

export function useAuthStatus(polling = false) {
  return useQuery({
    queryKey: AUTH_KEY,
    queryFn: getAuthStatus,
    staleTime: polling ? 0 : 60_000,
    refetchInterval: polling ? 3_000 : false,
  });
}

export function useAuthLogin() {
  return useMutation({
    mutationFn: startAuthLogin,
  });
}

export function useAuthCallback() {
  return useMutation({
    mutationFn: (code: string) => submitAuthCode(code),
  });
}

export function useAuthLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: authLogout,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: AUTH_KEY });
    },
  });
}
