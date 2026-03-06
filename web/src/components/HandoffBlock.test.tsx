import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HandoffBlock } from "./HandoffBlock";
import type { HandoffItem } from "../types";

function makeItem(overrides: Partial<HandoffItem> = {}): HandoffItem {
  return {
    id: "h-1",
    itemType: "sub_agent_turn",
    agentName: "Reviewer",
    content: "Reviewing code...",
    created_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("HandoffBlock", () => {
  it("renders handoff_start separator", () => {
    const item = makeItem({
      itemType: "handoff_start",
      fromAgent: "Developer",
      toAgent: "Reviewer",
    });
    render(<HandoffBlock item={item} />);
    expect(screen.getByText(/Developer → Reviewer/)).toBeInTheDocument();
  });

  it("renders sub_agent_turn with agent name", () => {
    const item = makeItem({
      itemType: "sub_agent_turn",
      agentName: "Reviewer",
      content: "Looking at the code...",
    });
    render(<HandoffBlock item={item} />);
    expect(screen.getByText("Reviewer")).toBeInTheDocument();
    expect(screen.getByText("Looking at the code...")).toBeInTheDocument();
    expect(screen.getByText("typing...")).toBeInTheDocument();
  });

  it("renders handoff_done with checkmark", () => {
    const item = makeItem({
      itemType: "handoff_done",
      agentName: "Reviewer",
      content: "Done reviewing.",
    });
    render(<HandoffBlock item={item} />);
    expect(screen.getByText("Reviewer")).toBeInTheDocument();
    expect(screen.getByText(/✓ Reviewer done/)).toBeInTheDocument();
  });

  it("renders cycle warning", () => {
    const item = makeItem({
      itemType: "handoff_cycle",
      agentName: "system",
      content: "Cycle detected: Developer → Reviewer → Developer → Reviewer",
    });
    render(<HandoffBlock item={item} />);
    expect(screen.getByText(/Cycle detected/)).toBeInTheDocument();
  });

  it("renders tool uses inside sub_agent_turn", () => {
    const item = makeItem({
      itemType: "sub_agent_turn",
      agentName: "Reviewer",
      content: "Checking file...",
      toolUses: [
        {
          tool_name: "Read",
          tool_input: { file_path: "src/users.ts" },
          result: "file contents here",
        },
      ],
    });
    render(<HandoffBlock item={item} />);
    expect(screen.getByText("Read")).toBeInTheDocument();
  });
});
