import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AgentLinkForm } from "./AgentLinkForm";
import type { Agent } from "../types";

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
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

const agents = [
  makeAgent({ id: "agent-1", name: "Coder" }),
  makeAgent({ id: "agent-2", name: "Reviewer" }),
];

describe("AgentLinkForm", () => {
  it("renders form fields", () => {
    render(
      <AgentLinkForm
        agents={agents}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        isLoading={false}
        error={null}
      />,
    );
    expect(screen.getByText("New Link")).toBeInTheDocument();
    expect(screen.getByText("Create Link")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });

  it("renders agent options in dropdowns", () => {
    render(
      <AgentLinkForm
        agents={agents}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        isLoading={false}
        error={null}
      />,
    );
    const options = screen.getAllByText("Coder");
    expect(options.length).toBeGreaterThanOrEqual(1);
  });

  it("calls onCancel when cancel button is clicked", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(
      <AgentLinkForm
        agents={agents}
        onSubmit={vi.fn()}
        onCancel={onCancel}
        isLoading={false}
        error={null}
      />,
    );
    await user.click(screen.getByText("Cancel"));
    expect(onCancel).toHaveBeenCalled();
  });

  it("calls onSubmit with selected values", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <AgentLinkForm
        agents={agents}
        onSubmit={onSubmit}
        onCancel={vi.fn()}
        isLoading={false}
        error={null}
      />,
    );

    const selects = screen.getAllByRole("combobox");
    // selects: [from, to, type]
    await user.selectOptions(selects[0]!, "agent-1");
    await user.selectOptions(selects[1]!, "agent-2");
    await user.selectOptions(selects[2]!, "review");

    await user.click(screen.getByText("Create Link"));
    expect(onSubmit).toHaveBeenCalledWith({
      from_agent_id: "agent-1",
      to_agent_id: "agent-2",
      link_type: "review",
    });
  });

  it("shows error message when provided", () => {
    render(
      <AgentLinkForm
        agents={agents}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        isLoading={false}
        error="Duplicate link"
      />,
    );
    expect(screen.getByText("Duplicate link")).toBeInTheDocument();
  });

  it("filters selected from-agent out of to-agent options", async () => {
    const user = userEvent.setup();
    render(
      <AgentLinkForm
        agents={agents}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        isLoading={false}
        error={null}
      />,
    );

    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0]!, "agent-1");

    // "To" dropdown should not contain "Coder" (agent-1)
    const toOptions = Array.from((selects[1] as HTMLSelectElement).options);
    const toValues = toOptions.map((o) => o.value).filter((v) => v !== "");
    expect(toValues).not.toContain("agent-1");
    expect(toValues).toContain("agent-2");
  });

  it("shows loading state", () => {
    render(
      <AgentLinkForm
        agents={agents}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        isLoading={true}
        error={null}
      />,
    );
    expect(screen.getByText("Creating...")).toBeInTheDocument();
  });
});
