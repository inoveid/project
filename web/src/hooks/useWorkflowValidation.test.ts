import { describe, expect, it } from "vitest";
import type { Agent, Workflow, WorkflowEdge } from "../types";
import { validateWorkflow, validateAll } from "./useWorkflowValidation";

function makeWorkflow(overrides: Partial<Workflow> = {}): Workflow {
  return {
    id: "wf-1",
    name: "Test Workflow",
    description: null,
    team_id: "team-1",
    starting_agent_id: "agent-1",
    starting_prompt: "Start here",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
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
    max_cycles: 3,
    position_x: null,
    position_y: null,
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
    requires_approval: true,
    created_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("validateWorkflow", () => {
  it("returns error when starting_prompt is empty", () => {
    const wf = makeWorkflow({ starting_prompt: "" });
    const issues = validateWorkflow(wf, [], [makeAgent()]);
    const errors = issues.filter((i) => i.type === "error");
    expect(errors).toHaveLength(1);
    expect(errors[0].message).toContain("starting prompt");
  });

  it("returns no issues for valid workflow", () => {
    const wf = makeWorkflow();
    const agents = [
      makeAgent({ id: "agent-1" }),
      makeAgent({ id: "agent-2" }),
    ];
    const edges = [makeEdge()];
    const issues = validateWorkflow(wf, edges, agents);
    expect(issues).toHaveLength(0);
  });

  it("warns about unreachable agent", () => {
    const wf = makeWorkflow({ starting_agent_id: "agent-1" });
    const agents = [
      makeAgent({ id: "agent-1" }),
      makeAgent({ id: "agent-2" }),
      makeAgent({ id: "agent-3" }),
    ];
    // agent-3 has outgoing but no incoming and is not starting
    const edges = [
      makeEdge({ from_agent_id: "agent-1", to_agent_id: "agent-2" }),
      makeEdge({ id: "e2", from_agent_id: "agent-3", to_agent_id: "agent-2" }),
    ];
    const issues = validateWorkflow(wf, edges, agents);
    const unreachable = issues.filter((i) => i.type === "warning" && i.nodeId === "agent-3");
    expect(unreachable).toHaveLength(1);
    expect(unreachable[0].message).toContain("unreachable");
  });

  it("warns when starting agent is alone with no edges", () => {
    const wf = makeWorkflow({ starting_agent_id: "agent-1" });
    const agents = [makeAgent({ id: "agent-1" })];
    const issues = validateWorkflow(wf, [], agents);
    const lonely = issues.filter((i) => i.type === "warning" && i.nodeId === "agent-1");
    expect(lonely).toHaveLength(1);
  });
});

describe("validateAll", () => {
  it("adds info issue for team with no agents", () => {
    const issues = validateAll([], [], [], ["team-1"]);
    const info = issues.filter((i) => i.type === "info");
    expect(info).toHaveLength(1);
    expect(info[0].message).toContain("no agents");
  });

  it("adds info issue for team with agents but no workflows", () => {
    const agents = [makeAgent({ team_id: "team-1" })];
    const issues = validateAll([], [], agents, ["team-1"]);
    const info = issues.filter((i) => i.type === "info");
    expect(info).toHaveLength(1);
    expect(info[0].message).toContain("no workflows");
  });

  it("does not add info for team with agents and workflows", () => {
    const agents = [makeAgent({ team_id: "team-1" })];
    const wfs = [makeWorkflow({ team_id: "team-1" })];
    const issues = validateAll(wfs, [], agents, ["team-1"]);
    const info = issues.filter((i) => i.type === "info");
    expect(info).toHaveLength(0);
  });

  it("warns about agent not part of any workflow", () => {
    const wf = makeWorkflow({ starting_agent_id: "agent-1" });
    const agents = [
      makeAgent({ id: "agent-1" }),
      makeAgent({ id: "agent-2", name: "Idle" }),
    ];
    const edges = [
      makeEdge({ from_agent_id: "agent-1", to_agent_id: "agent-3" }),
    ];
    const issues = validateAll([wf], edges, agents, ["team-1"]);
    const notInWf = issues.filter(
      (i) => i.type === "warning" && i.nodeId === "agent-2",
    );
    expect(notInWf).toHaveLength(1);
    expect(notInWf[0].message).toContain("not part of any workflow");
  });

  it("does not warn about idle agent when team has no workflows", () => {
    const agents = [makeAgent({ id: "agent-1" })];
    const issues = validateAll([], [], agents, ["team-1"]);
    const warnings = issues.filter((i) => i.type === "warning");
    expect(warnings).toHaveLength(0);
  });
});
