import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChatPage } from "./ChatPage";
import * as sessionsApi from "../api/sessions";
import type { Session, SessionListItem } from "../types";

vi.mock("../api/sessions", () => ({
  getSession: vi.fn(),
  getSessions: vi.fn(),
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

const mockSession2: Session = {
  id: "session-2",
  agent_id: "agent-2",
  status: "active",
  claude_session_id: null,
  created_at: "2024-01-01T00:01:00Z",
  stopped_at: null,
  messages: [
    {
      id: "msg-2",
      session_id: "session-2",
      role: "user",
      content: "World",
      tool_uses: null,
      created_at: "2024-01-01T00:01:00Z",
    },
  ],
};

const mockSessionsList: SessionListItem[] = [
  {
    id: "session-1",
    agent_id: "agent-1",
    agent_name: "Agent One",
    status: "active",
    created_at: "2024-01-01T00:00:00Z",
    stopped_at: null,
  },
  {
    id: "session-2",
    agent_id: "agent-2",
    agent_name: "Agent Two",
    status: "active",
    created_at: "2024-01-01T00:01:00Z",
    stopped_at: null,
  },
];

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
  it("shows sidebar with sessions", async () => {
    vi.mocked(sessionsApi.getSession).mockResolvedValue(mockSession);
    vi.mocked(sessionsApi.getSessions).mockResolvedValue(mockSessionsList);
    renderChatPage();

    expect(await screen.findByText("Sessions")).toBeInTheDocument();
  });

  it("renders main chat panel with session messages", async () => {
    vi.mocked(sessionsApi.getSession).mockResolvedValue(mockSession);
    vi.mocked(sessionsApi.getSessions).mockResolvedValue(mockSessionsList);
    renderChatPage();

    expect(await screen.findByText("Hello")).toBeInTheDocument();
  });

  it("opens side panel on 'Open side-by-side' click", async () => {
    vi.mocked(sessionsApi.getSession).mockImplementation((id: string) => {
      if (id === "session-1") return Promise.resolve(mockSession);
      if (id === "session-2") return Promise.resolve(mockSession2);
      return Promise.reject(new Error("Unknown"));
    });
    vi.mocked(sessionsApi.getSessions).mockResolvedValue(mockSessionsList);
    renderChatPage();

    const sideBtns = await screen.findAllByText("Open side-by-side");
    // Click the second session's side button (the one inside session-2 container)
    const btn = sideBtns.find((b) => {
      const container = b.closest("[data-session-id]");
      return container?.getAttribute("data-session-id") === "session-2";
    });
    expect(btn).toBeTruthy();
    fireEvent.click(btn!);

    expect(await screen.findByText("World")).toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("shows missing session ID message", () => {
    vi.mocked(sessionsApi.getSessions).mockResolvedValue([]);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/chat/"]}>
          <Routes>
            <Route path="/chat/" element={<ChatPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByText("Missing session ID")).toBeInTheDocument();
  });
});
