import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SessionList } from "./SessionList";
import * as sessionsApi from "../api/sessions";

vi.mock("../api/sessions", () => ({
  getSessions: vi.fn(),
}));

function renderSessionList() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SessionList />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SessionList", () => {
  it("renders nothing when no sessions", async () => {
    vi.mocked(sessionsApi.getSessions).mockResolvedValue([]);
    const { container } = renderSessionList();
    // Wait for query to resolve
    await vi.waitFor(() => {
      expect(sessionsApi.getSessions).toHaveBeenCalled();
    });
    expect(container.textContent).toBe("");
  });

  it("renders active sessions with links", async () => {
    vi.mocked(sessionsApi.getSessions).mockResolvedValue([
      {
        id: "abc12345-session-id",
        agent_id: "agent-1",
        status: "active",
        created_at: "2024-01-01T00:00:00Z",
        stopped_at: null,
      },
    ]);

    renderSessionList();
    expect(await screen.findByText("Active Sessions")).toBeInTheDocument();
    expect(screen.getByText("abc12345...")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });
});
