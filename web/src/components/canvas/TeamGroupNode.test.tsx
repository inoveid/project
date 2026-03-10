import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TeamGroupNode } from "./TeamGroupNode";
import type { Team } from "../../types";
import type { TeamGroupNodeData } from "./types";

function makeTeam(overrides: Partial<Team> = {}): Team {
  return {
    id: "team-1",
    name: "Dev Team",
    description: null,
    project_scoped: false,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    agents_count: 0,
    ...overrides,
  };
}

function renderNode(data: TeamGroupNodeData) {
  return render(<TeamGroupNode {...({ data } as never)} />);
}

describe("TeamGroupNode", () => {
  it("renders team name", () => {
    renderNode({ team: makeTeam(), agentCount: 3, validationIssues: [], isLocked: false });
    expect(screen.getByText("Dev Team")).toBeInTheDocument();
  });

  it("renders agent count plural", () => {
    renderNode({ team: makeTeam(), agentCount: 3, validationIssues: [], isLocked: false });
    expect(screen.getByText("3 agents")).toBeInTheDocument();
  });

  it("renders agent count singular", () => {
    renderNode({ team: makeTeam(), agentCount: 1, validationIssues: [], isLocked: false });
    expect(screen.getByText("1 agent")).toBeInTheDocument();
  });

  it("renders + Agent button that calls onAddAgent", () => {
    const onAddAgent = vi.fn();
    renderNode({ team: makeTeam(), agentCount: 0, onAddAgent, validationIssues: [], isLocked: false });
    const button = screen.getByText("+ Agent");
    fireEvent.click(button);
    expect(onAddAgent).toHaveBeenCalledWith("team-1");
  });

  it("renders + Workflow button that calls onAddWorkflow", () => {
    const onAddWorkflow = vi.fn();
    renderNode({ team: makeTeam(), agentCount: 0, onAddWorkflow, validationIssues: [], isLocked: false });
    const button = screen.getByText("+ Workflow");
    fireEvent.click(button);
    expect(onAddWorkflow).toHaveBeenCalledWith("team-1");
  });

  it("shows lock badge when isLocked", () => {
    renderNode({ team: makeTeam(), agentCount: 2, validationIssues: [], isLocked: true });
    expect(screen.getByTestId("lock-badge")).toBeInTheDocument();
    expect(screen.getByText("In progress")).toBeInTheDocument();
  });

  it("does not show lock badge when not locked", () => {
    renderNode({ team: makeTeam(), agentCount: 2, validationIssues: [], isLocked: false });
    expect(screen.queryByTestId("lock-badge")).not.toBeInTheDocument();
  });

  it("shows info messages for validation issues", () => {
    renderNode({
      team: makeTeam(),
      agentCount: 0,
      validationIssues: [{ type: "info", message: "Team has no agents" }],
      isLocked: false,
    });
    expect(screen.getByText("Team has no agents")).toBeInTheDocument();
  });
});
