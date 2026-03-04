import { render, screen, act, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChatPage } from "./ChatPage";
import * as sessionsApi from "../api/sessions";
import type { Session } from "../types";

vi.mock("../api/sessions", () => ({
  getSession: vi.fn(),
  stopSession: vi.fn(),
}));

// Mock WebSocket to prevent real connections
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
    {
      id: "msg-2",
      session_id: "session-1",
      role: "assistant",
      content: "Hi there!",
      tool_uses: null,
      created_at: "2024-01-01T00:00:01Z",
    },
  ],
};

function renderChatPage(sessionId = "session-1") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/chat/${sessionId}`]}>
        <Routes>
          <Route path="/chat/:sessionId" element={<ChatPage />} />
          <Route path="/" element={<div>Dashboard</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ChatPage", () => {
  it("shows loading state initially", () => {
    vi.mocked(sessionsApi.getSession).mockReturnValue(new Promise(() => {}));
    renderChatPage();
    expect(screen.getByText("Loading session...")).toBeInTheDocument();
  });

  it("shows error when session fails to load", async () => {
    vi.mocked(sessionsApi.getSession).mockRejectedValue(
      new Error("Not found"),
    );
    renderChatPage();
    expect(
      await screen.findByText(/Failed to load session/),
    ).toBeInTheDocument();
  });

  it("renders chat history after session loads", async () => {
    vi.mocked(sessionsApi.getSession).mockResolvedValue(mockSession);
    renderChatPage();

    expect(await screen.findByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("Hi there!")).toBeInTheDocument();
  });

  it("renders status indicator and stop button", async () => {
    vi.mocked(sessionsApi.getSession).mockResolvedValue(mockSession);
    renderChatPage();

    await screen.findByText("Hello");
    expect(screen.getByText("Stop")).toBeInTheDocument();
    expect(screen.getByText("Chat")).toBeInTheDocument();
  });

  it("sends a message via the input form", async () => {
    vi.mocked(sessionsApi.getSession).mockResolvedValue(mockSession);
    renderChatPage();
    await screen.findByText("Hello");

    // Connect WS
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

  it("disables input when not connected", async () => {
    vi.mocked(sessionsApi.getSession).mockResolvedValue(mockSession);
    renderChatPage();
    await screen.findByText("Hello");

    // WS not yet open — input should be disabled
    const input = screen.getByPlaceholderText("Type a message...");
    expect(input).toBeDisabled();
  });
});
