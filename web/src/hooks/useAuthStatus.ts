import { useQuery } from "@tanstack/react-query";
import { getAuthStatus } from "../api/auth";
import type { AuthStatus } from "../types";

export interface UseAuthStatusResult {
  authStatus: AuthStatus | undefined;
  isLoading: boolean;
}

export function useAuthStatus(): UseAuthStatusResult {
  const { data: authStatus, isLoading } = useQuery({
    queryKey: ["auth", "status"],
    queryFn: getAuthStatus,
    refetchInterval: 10_000,
  });

  return { authStatus, isLoading };
}
