import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SessionList } from "./SessionList";
import * as sessionsApi from "../api/sessions";

vi.mock("../api/sessions", () => ({
  getSessions: vi.fn(),
}));

function renderSessionList(props: {
  onSelectSession?: (id: string) => void;
  onOpenSide?: (id: string) => void;
  activeSessionIds?: string[];
} = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <SessionList
        onSelectSession={props.onSelectSession ?? vi.fn()}
        onOpenSide={props.onOpenSide}
        activeSessionIds={props.activeSessionIds}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SessionList", () => {
  it("shows loading state", () => {
    vi.mocked(sessionsApi.getSessions).mockReturnValue(new Promise(() => {}));
    renderSessionList();
    expect(screen.getByText("Loading sessions...")).toBeInTheDocument();
  });

  it("renders empty state when no sessions", async () => {
    vi.mocked(sessionsApi.getSessions).mockResolvedValue([]);
    renderSessionList();
    expect(
      await screen.findByText("No active sessions"),
    ).toBeInTheDocument();
  });

  it("renders active sessions", async () => {
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
    expect(await screen.findByText("Sessions")).toBeInTheDocument();
    expect(screen.getByText("abc12345...")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("calls onSelectSession on click", async () => {
    const onSelect = vi.fn();
    vi.mocked(sessionsApi.getSessions).mockResolvedValue([
      {
        id: "abc12345-session-id",
        agent_id: "agent-1",
        status: "active",
        created_at: "2024-01-01T00:00:00Z",
        stopped_at: null,
      },
    ]);

    renderSessionList({ onSelectSession: onSelect });
    const item = await screen.findByText("abc12345...");
    fireEvent.click(item);
    expect(onSelect).toHaveBeenCalledWith("abc12345-session-id");
  });

  it("shows open side-by-side button when onOpenSide provided", async () => {
    const onOpenSide = vi.fn();
    vi.mocked(sessionsApi.getSessions).mockResolvedValue([
      {
        id: "abc12345-session-id",
        agent_id: "agent-1",
        status: "active",
        created_at: "2024-01-01T00:00:00Z",
        stopped_at: null,
      },
    ]);

    renderSessionList({ onOpenSide });
    const btn = await screen.findByText("Open side-by-side");
    fireEvent.click(btn);
    expect(onOpenSide).toHaveBeenCalledWith("abc12345-session-id");
  });

  it("highlights active sessions", async () => {
    vi.mocked(sessionsApi.getSessions).mockResolvedValue([
      {
        id: "abc12345-session-id",
        agent_id: "agent-1",
        status: "active",
        created_at: "2024-01-01T00:00:00Z",
        stopped_at: null,
      },
    ]);

    renderSessionList({ activeSessionIds: ["abc12345-session-id"] });
    const item = await screen.findByText("abc12345...");
    const container = item.closest("[role='button']");
    expect(container?.className).toContain("border-blue-400");
  });
});
