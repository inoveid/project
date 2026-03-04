import { render, screen, act, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChatPanel } from "./ChatPanel";
import * as sessionsApi from "../api/sessions";
import type { Session } from "../types";

vi.mock("../api/sessions", () => ({
  getSession: vi.fn(),
  stopSession: vi.fn(),
}));

const wsInstances: MockWs[] = [];

class MockWs {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  readyState = 0;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];

  constructor() {
    wsInstances.push(this);
  }

  send(data: string) { this.sent.push(data); }
  close() { this.readyState = 3; }
  simulateOpen() {
    this.readyState = 1;
    this.onopen?.();
  }
}

beforeEach(() => {
  vi.clearAllMocks();
  wsInstances.length = 0;
  vi.stubGlobal("WebSocket", MockWs);
  vi.stubGlobal("crypto", { randomUUID: () => `uuid-${Math.random()}` });
});

const mockSession: Session = {
  id: "session-1",
  agent_id: "agent-1",
  status: "active",
  claude_session_id: null,
  created_at: "2024-01-01T00:00:00Z",
  stopped_at: null,
  messages: [
    {
      id: "msg-1",
      session_id: "session-1",
      role: "user",
      content: "Hello",
      tool_uses: null,
      created_at: "2024-01-01T00:00:00Z",
    },
  ],
};

function renderPanel(props: { sessionId?: string; onClose?: () => void; showClose?: boolean } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChatPanel
        sessionId={props.sessionId ?? "session-1"}
        onClose={props.onClose}
        showClose={props.showClose}
      />
    </QueryClientProvider>,
  );
}

describe("ChatPanel", () => {
  it("shows loading state", () => {
    vi.mocked(sessionsApi.getSession).mockReturnValue(new Promise(() => {}));
    renderPanel();
    expect(screen.getByText("Loading session...")).toBeInTheDocument();
  });

  it("shows error when session fails to load", async () => {
    vi.mocked(sessionsApi.getSession).mockRejectedValue(new Error("Not found"));
    renderPanel();
    expect(
      await screen.findByText(/Failed to load session/),
    ).toBeInTheDocument();
  });

  it("renders messages after session loads", async () => {
    vi.mocked(sessionsApi.getSession).mockResolvedValue(mockSession);
    renderPanel();
    expect(await screen.findByText("Hello")).toBeInTheDocument();
  });

  it("shows close button when showClose is true", async () => {
    const onClose = vi.fn();
    vi.mocked(sessionsApi.getSession).mockResolvedValue(mockSession);
    renderPanel({ showClose: true, onClose });
    const closeBtn = await screen.findByText("Close");
    closeBtn.click();
    expect(onClose).toHaveBeenCalled();
  });

  it("sends a message via the input form", async () => {
    vi.mocked(sessionsApi.getSession).mockResolvedValue(mockSession);
    renderPanel();
    await screen.findByText("Hello");

    const ws = wsInstances[wsInstances.length - 1];
    await act(async () => {
      ws?.simulateOpen();
    });

    const input = screen.getByPlaceholderText("Type a message...");
    await waitFor(() => expect(input).not.toBeDisabled());

    const user = userEvent.setup();
    await user.type(input, "How are you?");
    await user.click(screen.getByText("Send"));

    expect(screen.getByText("How are you?")).toBeInTheDocument();
  });
});
