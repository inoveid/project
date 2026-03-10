import { describe, expect, it } from "vitest";
import type { Agent, Team, Workflow, WorkflowEdge } from "../../types";
import {
  getWorkflowColor,
  buildWorkflowColorMap,
  buildCanvasLayout,
  applyWorkflowFilter,
} from "./canvasUtils";

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
    starting_prompt: "Start",
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

describe("getWorkflowColor", () => {
  it("returns a color string", () => {
    const color = getWorkflowColor(0);
    expect(color).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("wraps around for large indices", () => {
    const color0 = getWorkflowColor(0);
    const color8 = getWorkflowColor(8);
    expect(color8).toBe(color0);
  });
});

describe("buildWorkflowColorMap", () => {
  it("maps each workflow to a color", () => {
    const workflows = [makeWorkflow({ id: "wf-1" }), makeWorkflow({ id: "wf-2" })];
    const map = buildWorkflowColorMap(workflows);
    expect(map.size).toBe(2);
    expect(map.get("wf-1")).toBeDefined();
    expect(map.get("wf-2")).toBeDefined();
    expect(map.get("wf-1")).not.toBe(map.get("wf-2"));
  });
});

describe("buildCanvasLayout", () => {
  it("creates group node for each team", () => {
    const teams = [makeTeam({ id: "team-1" }), makeTeam({ id: "team-2" })];
    const agentsByTeam = new Map<string, Agent[]>();
    const { nodes } = buildCanvasLayout(teams, agentsByTeam, [], [], new Map(), new Set());
    const groupNodes = nodes.filter((n) => n.type === "teamGroup");
    expect(groupNodes).toHaveLength(2);
  });

  it("creates agent node for each agent", () => {
    const teams = [makeTeam()];
    const agents = [makeAgent({ id: "a1" }), makeAgent({ id: "a2" })];
    const agentsByTeam = new Map([["team-1", agents]]);
    const { nodes } = buildCanvasLayout(teams, agentsByTeam, [], [], new Map(), new Set());
    const agentNodes = nodes.filter((n) => n.type === "agentNode");
    expect(agentNodes).toHaveLength(2);
  });

  it("marks starting agent as isStart", () => {
    const teams = [makeTeam()];
    const agents = [makeAgent({ id: "agent-1" })];
    const agentsByTeam = new Map([["team-1", agents]]);
    const workflows = [makeWorkflow({ starting_agent_id: "agent-1" })];
    const { nodes } = buildCanvasLayout(teams, agentsByTeam, workflows, [], new Map(), new Set());
    const agentNode = nodes.find((n) => n.id === "agent-agent-1");
    expect(agentNode?.data.isStart).toBe(true);
  });

  it("marks agent with no outgoing edges as isEnd", () => {
    const teams = [makeTeam()];
    const agents = [makeAgent({ id: "agent-1" }), makeAgent({ id: "agent-2" })];
    const agentsByTeam = new Map([["team-1", agents]]);
    const edges = [makeEdge({ from_agent_id: "agent-1", to_agent_id: "agent-2" })];
    const { nodes } = buildCanvasLayout(teams, agentsByTeam, [], edges, new Map(), new Set());
    const endNode = nodes.find((n) => n.id === "agent-agent-2");
    expect(endNode?.data.isEnd).toBe(true);
  });

  it("creates edge for each workflow edge", () => {
    const teams = [makeTeam()];
    const agents = [makeAgent({ id: "a1" }), makeAgent({ id: "a2" })];
    const agentsByTeam = new Map([["team-1", agents]]);
    const wfEdges = [makeEdge({ id: "e1" })];
    const colorMap = new Map([["wf-1", "#3b82f6"]]);
    const { edges } = buildCanvasLayout(teams, agentsByTeam, [], wfEdges, colorMap, new Set());
    expect(edges).toHaveLength(1);
    expect(edges[0]?.id).toBe("edge-e1");
  });

  it("uses agent position when provided", () => {
    const teams = [makeTeam()];
    const agents = [makeAgent({ id: "a1", position_x: 100, position_y: 200 })];
    const agentsByTeam = new Map([["team-1", agents]]);
    const { nodes } = buildCanvasLayout(teams, agentsByTeam, [], [], new Map(), new Set());
    const agentNode = nodes.find((n) => n.id === "agent-a1");
    expect(agentNode?.position).toEqual({ x: 100, y: 200 });
  });

  it("marks active agents", () => {
    const teams = [makeTeam()];
    const agents = [makeAgent({ id: "a1" })];
    const agentsByTeam = new Map([["team-1", agents]]);
    const activeIds = new Set(["a1"]);
    const { nodes } = buildCanvasLayout(teams, agentsByTeam, [], [], new Map(), activeIds);
    const agentNode = nodes.find((n) => n.id === "agent-a1");
    expect(agentNode?.data.isActive).toBe(true);
  });
});

describe("applyWorkflowFilter", () => {
  it("returns edges unchanged when no workflow selected", () => {
    const edges = [{ id: "edge-1", source: "a", target: "b", type: "workflowEdge", data: {}, style: {} }];
    const result = applyWorkflowFilter(edges, null, [], new Map());
    expect(result).toEqual(edges);
  });

  it("highlights selected workflow edges and dims others", () => {
    const edges = [
      { id: "edge-e1", source: "a", target: "b", type: "workflowEdge", data: {}, style: { stroke: "#3b82f6" } },
      { id: "edge-e2", source: "c", target: "d", type: "workflowEdge", data: {}, style: { stroke: "#10b981" } },
    ];
    const wfEdges = [
      makeEdge({ id: "e1", workflow_id: "wf-1" }),
      makeEdge({ id: "e2", workflow_id: "wf-2" }),
    ];
    const colorMap = new Map([["wf-1", "#3b82f6"]]);
    const result = applyWorkflowFilter(edges, "wf-1", wfEdges, colorMap);
    expect(result[0]?.style?.strokeWidth).toBe(3);
    expect(result[0]?.style?.opacity).toBe(1);
    expect(result[1]?.style?.opacity).toBe(0.4);
  });
});
