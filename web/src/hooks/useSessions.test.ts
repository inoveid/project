import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { useSessions } from "./useSessions";
import * as sessionsApi from "../api/sessions";
import type { ReactNode } from "react";
import { createElement } from "react";

vi.mock("../api/sessions", () => ({
  getSessions: vi.fn(),
  createSession: vi.fn(),
  getSession: vi.fn(),
  stopSession: vi.fn(),
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useSessions", () => {
  it("fetches active sessions", async () => {
    const sessions = [
      {
        id: "s1",
        agent_id: "a1",
        agent_name: "Agent One",
        status: "active" as const,
        created_at: "2024-01-01T00:00:00Z",
        stopped_at: null,
      },
    ];
    vi.mocked(sessionsApi.getSessions).mockResolvedValue(sessions);

    const { result } = renderHook(() => useSessions(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(sessions);
  });
});
