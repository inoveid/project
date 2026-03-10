import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TeamGroupNode } from "./TeamGroupNode";
import type { Team } from "../../types";
import type { TeamGroupNodeData } from "./TeamGroupNode";

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
    renderNode({ team: makeTeam(), agentCount: 3 });
    expect(screen.getByText("Dev Team")).toBeInTheDocument();
  });

  it("renders agent count plural", () => {
    renderNode({ team: makeTeam(), agentCount: 3 });
    expect(screen.getByText("3 agents")).toBeInTheDocument();
  });

  it("renders agent count singular", () => {
    renderNode({ team: makeTeam(), agentCount: 1 });
    expect(screen.getByText("1 agent")).toBeInTheDocument();
  });

  it("renders disabled Add Agent button", () => {
    renderNode({ team: makeTeam(), agentCount: 0 });
    const button = screen.getByText("+ Agent");
    expect(button).toBeDisabled();
  });
});
