import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AgentLinkList } from "./AgentLinkList";
import type { Agent, AgentLink } from "../types";

function makeAgent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: "agent-1",
    team_id: "team-1",
    name: "Coder",
    role: "developer",
    description: null,
    system_prompt: "prompt",
    allowed_tools: [],
    config: {},
    max_cycles: 10,
    position_x: null,
    position_y: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeLink(overrides: Partial<AgentLink> = {}): AgentLink {
  return {
    id: "link-1",
    team_id: "team-1",
    from_agent_id: "agent-1",
    to_agent_id: "agent-2",
    link_type: "handoff",
    created_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

const agents = [
  makeAgent({ id: "agent-1", name: "Coder" }),
  makeAgent({ id: "agent-2", name: "Reviewer" }),
];

describe("AgentLinkList", () => {
  it("shows empty message when no links", () => {
    render(<AgentLinkList links={[]} agents={agents} onDelete={vi.fn()} />);
    expect(screen.getByText("No links yet.")).toBeInTheDocument();
  });

  it("renders link rows with agent names", () => {
    const link = makeLink();
    render(<AgentLinkList links={[link]} agents={agents} onDelete={vi.fn()} />);
    expect(screen.getByText("Coder")).toBeInTheDocument();
    expect(screen.getByText("Reviewer")).toBeInTheDocument();
    expect(screen.getByText("handoff")).toBeInTheDocument();
  });

  it("shows Unknown for missing agent", () => {
    const link = makeLink({ from_agent_id: "missing-id" });
    render(<AgentLinkList links={[link]} agents={agents} onDelete={vi.fn()} />);
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });

  it("calls onDelete when delete button is clicked", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    const link = makeLink();
    render(<AgentLinkList links={[link]} agents={agents} onDelete={onDelete} />);
    await user.click(screen.getByText("Delete"));
    expect(onDelete).toHaveBeenCalledWith("link-1");
  });

  it("renders multiple links", () => {
    const links = [
      makeLink({ id: "link-1", link_type: "handoff" }),
      makeLink({ id: "link-2", link_type: "review" }),
    ];
    render(<AgentLinkList links={links} agents={agents} onDelete={vi.fn()} />);
    expect(screen.getByText("handoff")).toBeInTheDocument();
    expect(screen.getByText("review")).toBeInTheDocument();
  });
});
