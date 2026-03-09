import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useAuthStatus } from "./useAuthStatus";
import * as authApi from "../api/auth";

vi.mock("../api/auth");

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useAuthStatus", () => {
  it("returns auth status when authenticated", async () => {
    vi.mocked(authApi.getAuthStatus).mockResolvedValue({
      logged_in: true,
      email: "user@example.com",
      org_name: null,
      subscription_type: "pro",
      auth_method: "oauth",
    });

    const { result } = renderHook(() => useAuthStatus(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.authStatus?.logged_in).toBe(true);
  });

  it("returns logged_in=false when not authenticated", async () => {
    vi.mocked(authApi.getAuthStatus).mockResolvedValue({
      logged_in: false,
      email: null,
      org_name: null,
      subscription_type: null,
      auth_method: null,
    });

    const { result } = renderHook(() => useAuthStatus(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.authStatus?.logged_in).toBe(false);
  });
});
