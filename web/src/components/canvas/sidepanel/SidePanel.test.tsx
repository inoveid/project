import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SidePanel } from "./SidePanel";
import type { Agent, Workflow, WorkflowEdge } from "../../../types";

function makeAgent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: "agent-1",
    team_id: "team-1",
    name: "Coder",
    role: "developer",
    description: "Writes code",
    system_prompt: "prompt",
    allowed_tools: ["bash"],
    config: {},
    prompts: [],
    max_cycles: 10,
    position_x: null,
    position_y: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeWorkflow(overrides: Partial<Workflow> = {}): Workflow {
  return {
    id: "wf-1",
    name: "Default",
    description: null,
    team_id: "team-1",
    starting_agent_id: "agent-1",
    starting_prompt: "Do work",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeEdge(overrides: Partial<WorkflowEdge> = {}): WorkflowEdge {
  return {
    id: "edge-1",
    workflow_id: "wf-1",
    from_agent_id: "agent-1",
    to_agent_id: "agent-2",
    condition: null,
    prompt_template: null,
    prompt_id: null,
    order: 0,
    requires_approval: false,
    created_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

const defaultProps = {
  onClose: vi.fn(),
  onUpdateAgent: vi.fn(),
  onDeleteAgent: vi.fn(),
  onUpdateEdge: vi.fn(),
  onDeleteEdge: vi.fn(),
  onCreateEdge: vi.fn(),
};

describe("SidePanel", () => {
  it("renders agent panel with name", () => {
    render(
      <SidePanel
        {...defaultProps}
        selection={{ type: "agent", agentId: "agent-1" }}
        agents={[makeAgent()]}
        workflows={[makeWorkflow()]}
        workflowEdges={[]}
      />,
    );
    expect(screen.getByText("Coder")).toBeInTheDocument();
    expect(screen.getByTestId("side-panel")).toBeInTheDocument();
  });

  it("renders three tabs for agent", () => {
    render(
      <SidePanel
        {...defaultProps}
        selection={{ type: "agent", agentId: "agent-1" }}
        agents={[makeAgent()]}
        workflows={[]}
        workflowEdges={[]}
      />,
    );
    expect(screen.getByText("General")).toBeInTheDocument();
    expect(screen.getByText("Prompts")).toBeInTheDocument();
    expect(screen.getByText("Handoff")).toBeInTheDocument();
  });

  it("switches tabs on click", () => {
    render(
      <SidePanel
        {...defaultProps}
        selection={{ type: "agent", agentId: "agent-1" }}
        agents={[makeAgent()]}
        workflows={[]}
        workflowEdges={[]}
      />,
    );
    fireEvent.click(screen.getByText("Prompts"));
    expect(screen.getByText("+ Add prompt")).toBeInTheDocument();
  });

  it("renders edge panel for edge selection", () => {
    render(
      <SidePanel
        {...defaultProps}
        selection={{ type: "edge", edgeId: "edge-edge-1" }}
        agents={[makeAgent(), makeAgent({ id: "agent-2", name: "Reviewer" })]}
        workflows={[makeWorkflow()]}
        workflowEdges={[makeEdge()]}
      />,
    );
    expect(screen.getByText("Edge settings")).toBeInTheDocument();
    expect(screen.getByText("Condition")).toBeInTheDocument();
  });

  it("calls onClose when close button clicked", () => {
    const onClose = vi.fn();
    render(
      <SidePanel
        {...defaultProps}
        onClose={onClose}
        selection={{ type: "agent", agentId: "agent-1" }}
        agents={[makeAgent()]}
        workflows={[]}
        workflowEdges={[]}
      />,
    );
    fireEvent.click(screen.getByLabelText("Close panel"));
    expect(onClose).toHaveBeenCalled();
  });

  it("returns null for unknown agent", () => {
    const { container } = render(
      <SidePanel
        {...defaultProps}
        selection={{ type: "agent", agentId: "unknown" }}
        agents={[makeAgent()]}
        workflows={[]}
        workflowEdges={[]}
      />,
    );
    expect(container.firstChild).toBeNull();
  });
});
