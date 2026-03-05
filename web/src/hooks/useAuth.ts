import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  authLogout,
  getAuthStatus,
  startAuthLogin,
  submitAuthCode,
} from "../api/auth";

const AUTH_KEY = ["auth", "status"] as const;

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
