import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AgentCard } from "./AgentCard";
import type { Agent } from "../types";
import * as sessionsApi from "../api/sessions";

vi.mock("../api/sessions", () => ({
  createSession: vi.fn(),
  getSessions: vi.fn(),
  stopSession: vi.fn(),
}));

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

function makeAgent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: "agent-1",
    team_id: "team-1",
    name: "Coder",
    role: "developer",
    description: "Writes code",
    system_prompt: "prompt",
    allowed_tools: ["Read", "Write"],
    config: {},
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderCard(agent = makeAgent(), props: { onEdit?: (a: Agent) => void; onDelete?: (id: string) => void } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AgentCard agent={agent} onEdit={props.onEdit ?? vi.fn()} onDelete={props.onDelete ?? vi.fn()} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AgentCard", () => {
  it("renders agent name, role, and description", () => {
    renderCard();
    expect(screen.getByText("Coder")).toBeInTheDocument();
    expect(screen.getByText("developer")).toBeInTheDocument();
    expect(screen.getByText("Writes code")).toBeInTheDocument();
  });

  it("renders allowed tools", () => {
    renderCard();
    expect(screen.getByText("Read")).toBeInTheDocument();
    expect(screen.getByText("Write")).toBeInTheDocument();
  });

  it("renders Chat button", () => {
    renderCard();
    expect(screen.getByText("Chat")).toBeInTheDocument();
  });

  it("creates session and navigates on Chat click", async () => {
    const user = userEvent.setup();
    vi.mocked(sessionsApi.createSession).mockResolvedValueOnce({
      id: "session-123",
      agent_id: "agent-1",
      status: "active",
      claude_session_id: null,
      created_at: "2024-01-01T00:00:00Z",
      stopped_at: null,
    });

    renderCard();
    await user.click(screen.getByText("Chat"));

    await waitFor(() => {
      expect(sessionsApi.createSession).toHaveBeenCalledWith("agent-1");
      expect(mockNavigate).toHaveBeenCalledWith("/chat/session-123");
    });
  });

  it("shows Starting... while creating session", async () => {
    const user = userEvent.setup();
    vi.mocked(sessionsApi.createSession).mockReturnValueOnce(
      new Promise(() => {}) as Promise<never>,
    );

    renderCard();
    await user.click(screen.getByText("Chat"));

    expect(screen.getByText("Starting...")).toBeInTheDocument();
  });

  it("calls onEdit when Edit is clicked", async () => {
    const user = userEvent.setup();
    const onEdit = vi.fn();
    const agent = makeAgent();
    renderCard(agent, { onEdit });
    await user.click(screen.getByText("Edit"));
    expect(onEdit).toHaveBeenCalledWith(agent);
  });

  it("calls onDelete when Delete is clicked", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    renderCard(makeAgent(), { onDelete });
    await user.click(screen.getByText("Delete"));
    expect(onDelete).toHaveBeenCalledWith("agent-1");
  });
});
