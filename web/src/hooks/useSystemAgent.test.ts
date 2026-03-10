import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useSystemAgent } from "./useSystemAgent";
import * as agentsApi from "../api/agents";
import * as sessionsApi from "../api/sessions";

vi.mock("../api/agents");
vi.mock("../api/sessions");

const SYSTEM_SESSION_KEY = "system_agent_session_id";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe("useSystemAgent", () => {
  it("creates a new session when localStorage is empty", async () => {
    vi.mocked(agentsApi.getSystemAgent).mockResolvedValue({
      id: "agent-1",
      team_id: "team-1",
      name: "System",
      role: "system",
      description: null,
      system_prompt: "",
      allowed_tools: [],
      config: {},
      max_cycles: 10,
      position_x: null,
      position_y: null,
      created_at: "",
      updated_at: "",
    });
    vi.mocked(sessionsApi.createSession).mockResolvedValue({
      id: "session-new",
      agent_id: "agent-1",
      status: "active",
      claude_session_id: null,
      created_at: "",
      stopped_at: null,
    });

    const { result } = renderHook(() => useSystemAgent(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isReady).toBe(true));

    expect(result.current.sessionId).toBe("session-new");
    expect(localStorage.getItem(SYSTEM_SESSION_KEY)).toBe("session-new");
    expect(sessionsApi.createSession).toHaveBeenCalledWith("agent-1");
  });

  it("restores existing session from localStorage when valid", async () => {
    localStorage.setItem(SYSTEM_SESSION_KEY, "session-existing");
    vi.mocked(agentsApi.getSystemAgent).mockResolvedValue({
      id: "agent-1",
      team_id: "team-1",
      name: "System",
      role: "system",
      description: null,
      system_prompt: "",
      allowed_tools: [],
      config: {},
      max_cycles: 10,
      position_x: null,
      position_y: null,
      created_at: "",
      updated_at: "",
    });
    vi.mocked(sessionsApi.getSession).mockResolvedValue({
      id: "session-existing",
      agent_id: "agent-1",
      status: "active",
      claude_session_id: null,
      created_at: "",
      stopped_at: null,
    });

    const { result } = renderHook(() => useSystemAgent(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isReady).toBe(true));

    expect(result.current.sessionId).toBe("session-existing");
    expect(sessionsApi.createSession).not.toHaveBeenCalled();
  });

  it("creates new session when stored session_id is invalid", async () => {
    localStorage.setItem(SYSTEM_SESSION_KEY, "session-invalid");
    vi.mocked(agentsApi.getSystemAgent).mockResolvedValue({
      id: "agent-1",
      team_id: "team-1",
      name: "System",
      role: "system",
      description: null,
      system_prompt: "",
      allowed_tools: [],
      config: {},
      max_cycles: 10,
      position_x: null,
      position_y: null,
      created_at: "",
      updated_at: "",
    });
    vi.mocked(sessionsApi.getSession).mockRejectedValue(
      new Error("API error 404: not found"),
    );
    vi.mocked(sessionsApi.createSession).mockResolvedValue({
      id: "session-new",
      agent_id: "agent-1",
      status: "active",
      claude_session_id: null,
      created_at: "",
      stopped_at: null,
    });

    const { result } = renderHook(() => useSystemAgent(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isReady).toBe(true));

    expect(result.current.sessionId).toBe("session-new");
    expect(localStorage.getItem(SYSTEM_SESSION_KEY)).toBe("session-new");
  });

  it("resetSession clears localStorage and resets state", async () => {
    localStorage.setItem(SYSTEM_SESSION_KEY, "session-existing");
    vi.mocked(agentsApi.getSystemAgent).mockResolvedValue({
      id: "agent-1",
      team_id: "team-1",
      name: "System",
      role: "system",
      description: null,
      system_prompt: "",
      allowed_tools: [],
      config: {},
      max_cycles: 10,
      position_x: null,
      position_y: null,
      created_at: "",
      updated_at: "",
    });
    vi.mocked(sessionsApi.getSession).mockResolvedValue({
      id: "session-existing",
      agent_id: "agent-1",
      status: "active",
      claude_session_id: null,
      created_at: "",
      stopped_at: null,
    });
    vi.mocked(sessionsApi.createSession).mockResolvedValue({
      id: "session-fresh",
      agent_id: "agent-1",
      status: "active",
      claude_session_id: null,
      created_at: "",
      stopped_at: null,
    });

    const { result } = renderHook(() => useSystemAgent(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isReady).toBe(true));

    result.current.resetSession();

    expect(localStorage.getItem(SYSTEM_SESSION_KEY)).toBeNull();

    // After reset, a new session is created automatically
    await waitFor(() => expect(result.current.sessionId).toBe("session-fresh"));
    expect(result.current.isReady).toBe(true);
    expect(sessionsApi.createSession).toHaveBeenCalledTimes(1);
  });
});
