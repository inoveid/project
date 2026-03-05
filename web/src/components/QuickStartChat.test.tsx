import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { QuickStartChat } from "./QuickStartChat";
import * as agentsApi from "../api/agents";

vi.mock("../api/agents", () => ({
  getAllAgents: vi.fn(),
  getAgents: vi.fn(),
  getAgent: vi.fn(),
  createAgent: vi.fn(),
  updateAgent: vi.fn(),
  deleteAgent: vi.fn(),
}));

vi.mock("../api/sessions", () => ({
  createSession: vi.fn(),
  getSessions: vi.fn(),
  getSession: vi.fn(),
  stopSession: vi.fn(),
}));

vi.mock("../api/auth", () => ({
  getAuthStatus: vi.fn().mockResolvedValue({
    logged_in: true,
    email: "user@test.com",
    org_name: null,
    subscription_type: null,
    auth_method: null,
  }),
  startAuthLogin: vi.fn(),
  authLogout: vi.fn(),
}));

function renderComponent(onSessionCreated = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <QuickStartChat onSessionCreated={onSessionCreated} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("QuickStartChat", () => {
  it("shows empty state when no agents", async () => {
    vi.mocked(agentsApi.getAllAgents).mockResolvedValue([]);
    renderComponent();
    expect(
      await screen.findByText(/No agents available/),
    ).toBeInTheDocument();
  });

  it("renders agent select dropdown", async () => {
    vi.mocked(agentsApi.getAllAgents).mockResolvedValue([
      {
        id: "agent-1",
        team_id: "team-1",
        name: "Coder",
        role: "developer",
        description: null,
        system_prompt: "You are a coder",
        allowed_tools: [],
        config: {},
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    ]);
    renderComponent();
    expect(await screen.findByText("Select agent...")).toBeInTheDocument();
    expect(screen.getByText("Coder — developer")).toBeInTheDocument();
  });

  it("disables start button when no agent selected", async () => {
    vi.mocked(agentsApi.getAllAgents).mockResolvedValue([
      {
        id: "agent-1",
        team_id: "team-1",
        name: "Coder",
        role: "developer",
        description: null,
        system_prompt: "You are a coder",
        allowed_tools: [],
        config: {},
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    ]);
    renderComponent();
    const button = await screen.findByText("Start Chat");
    expect(button).toBeDisabled();
  });

  it("enables start button after selecting agent", async () => {
    vi.mocked(agentsApi.getAllAgents).mockResolvedValue([
      {
        id: "agent-1",
        team_id: "team-1",
        name: "Coder",
        role: "developer",
        description: null,
        system_prompt: "You are a coder",
        allowed_tools: [],
        config: {},
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    ]);
    renderComponent();
    const select = await screen.findByRole("combobox");
    fireEvent.change(select, { target: { value: "agent-1" } });
    expect(screen.getByText("Start Chat")).not.toBeDisabled();
  });
});
