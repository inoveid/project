import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConnectEdgeDialog } from "./ConnectEdgeDialog";
import type { Workflow } from "../../types";

function makeWorkflow(overrides: Partial<Workflow> = {}): Workflow {
  return {
    id: "wf-1",
    name: "Default Workflow",
    description: null,
    team_id: "team-1",
    starting_agent_id: "agent-1",
    starting_prompt: "Do work",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("ConnectEdgeDialog", () => {
  it("renders heading and agent names", () => {
    render(
      <ConnectEdgeDialog
        workflows={[makeWorkflow()]}
        fromAgentName="Coder"
        toAgentName="Reviewer"
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText("Create edge")).toBeInTheDocument();
  });

  it("calls onCancel when Cancel clicked", () => {
    const onCancel = vi.fn();
    render(
      <ConnectEdgeDialog
        workflows={[makeWorkflow()]}
        fromAgentName="Coder"
        toAgentName="Reviewer"
        onSubmit={vi.fn()}
        onCancel={onCancel}
      />,
    );
    fireEvent.click(screen.getByText("Cancel"));
    expect(onCancel).toHaveBeenCalled();
  });

  it("does not submit without workflow selection", () => {
    const onSubmit = vi.fn();
    render(
      <ConnectEdgeDialog
        workflows={[makeWorkflow()]}
        fromAgentName="Coder"
        toAgentName="Reviewer"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByText("Create"));
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
