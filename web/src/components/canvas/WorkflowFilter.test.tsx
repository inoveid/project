import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { WorkflowFilter } from "./WorkflowFilter";
import type { Workflow } from "../../types";

function makeWorkflow(overrides: Partial<Workflow> = {}): Workflow {
  return {
    id: "wf-1",
    name: "Default",
    description: null,
    team_id: "team-1",
    starting_agent_id: "agent-1",
    starting_prompt: "Start",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("WorkflowFilter", () => {
  it("renders nothing when no workflows", () => {
    const { container } = render(
      <WorkflowFilter workflows={[]} selectedId={null} onSelect={vi.fn()} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders All button and workflow buttons", () => {
    const workflows = [
      makeWorkflow({ id: "wf-1", name: "Pipeline A" }),
      makeWorkflow({ id: "wf-2", name: "Pipeline B" }),
    ];
    render(<WorkflowFilter workflows={workflows} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByText("All")).toBeInTheDocument();
    expect(screen.getByText("Pipeline A")).toBeInTheDocument();
    expect(screen.getByText("Pipeline B")).toBeInTheDocument();
  });

  it("calls onSelect with null when All is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const workflows = [makeWorkflow()];
    render(<WorkflowFilter workflows={workflows} selectedId="wf-1" onSelect={onSelect} />);
    await user.click(screen.getByText("All"));
    expect(onSelect).toHaveBeenCalledWith(null);
  });

  it("calls onSelect with workflow id when workflow button is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const workflows = [makeWorkflow({ id: "wf-1", name: "Pipeline A" })];
    render(<WorkflowFilter workflows={workflows} selectedId={null} onSelect={onSelect} />);
    await user.click(screen.getByText("Pipeline A"));
    expect(onSelect).toHaveBeenCalledWith("wf-1");
  });
});
