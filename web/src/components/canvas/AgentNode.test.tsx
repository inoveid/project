import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeAll } from "vitest";
import { ReactFlowProvider } from "@xyflow/react";
import { AgentNode } from "./AgentNode";
import type { Agent } from "../../types";
import type { AgentNodeData } from "./AgentNode";

beforeAll(() => {
  global.ResizeObserver = vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
  }));
});

function makeAgent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: "agent-1",
    team_id: "team-1",
    name: "Coder",
    role: "developer",
    description: "Writes code",
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

function renderNode(data: AgentNodeData) {
  return render(
    <ReactFlowProvider>
      <AgentNode {...({ data } as never)} />
    </ReactFlowProvider>,
  );
}

describe("AgentNode", () => {
  it("renders agent name", () => {
    renderNode({ agent: makeAgent(), isStart: false, isEnd: false, isActive: false });
    expect(screen.getByText("Coder")).toBeInTheDocument();
  });

  it("renders description when provided", () => {
    renderNode({ agent: makeAgent({ description: "Writes code" }), isStart: false, isEnd: false, isActive: false });
    expect(screen.getByText("Writes code")).toBeInTheDocument();
  });

  it("shows Start badge when isStart", () => {
    renderNode({ agent: makeAgent(), isStart: true, isEnd: false, isActive: false });
    expect(screen.getByText("Start")).toBeInTheDocument();
  });

  it("shows End badge when isEnd", () => {
    renderNode({ agent: makeAgent(), isStart: false, isEnd: true, isActive: false });
    expect(screen.getByText("End")).toBeInTheDocument();
  });

  it("does not show badges when not start or end", () => {
    renderNode({ agent: makeAgent(), isStart: false, isEnd: false, isActive: false });
    expect(screen.queryByText("Start")).not.toBeInTheDocument();
    expect(screen.queryByText("End")).not.toBeInTheDocument();
  });

  it("shows active indicator when isActive", () => {
    renderNode({ agent: makeAgent(), isStart: false, isEnd: false, isActive: true });
    expect(screen.getByTitle("Active")).toBeInTheDocument();
  });
});
