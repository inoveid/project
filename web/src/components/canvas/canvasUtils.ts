import type { Node, Edge } from "@xyflow/react";
import type { Agent, Team, ValidationIssue, Workflow, WorkflowEdge } from "../../types";
import type { AgentNodeData, TeamGroupNodeData } from "./types";

const WORKFLOW_COLORS = [
  "#3b82f6", // blue
  "#10b981", // emerald
  "#f59e0b", // amber
  "#ef4444", // red
  "#8b5cf6", // violet
  "#ec4899", // pink
  "#06b6d4", // cyan
  "#f97316", // orange
];

export function getWorkflowColor(index: number): string {
  return WORKFLOW_COLORS[index % WORKFLOW_COLORS.length] ?? "#94a3b8";
}

/** Strips "agent-" or "edge-" prefix from ReactFlow node/edge IDs to get the raw entity ID. */
export function stripNodePrefix(id: string, prefix: "agent-" | "edge-"): string {
  return id.startsWith(prefix) ? id.slice(prefix.length) : id;
}

const GROUP_PADDING = 40;
const NODE_WIDTH = 200;
const NODE_HEIGHT = 80;
const NODE_GAP_X = 60;
const NODE_GAP_Y = 40;
const GROUP_HEADER_HEIGHT = 50;
const GROUP_GAP = 60;

interface LayoutResult {
  nodes: Node[];
  edges: Edge[];
}

interface LayoutCallbacks {
  onAddAgent?: (teamId: string) => void;
  onAddWorkflow?: (teamId: string) => void;
}

interface ValidationContext {
  issuesByNode: Map<string, ValidationIssue[]>;
  lockedWorkflowIds: Set<string>;
}

const EMPTY_ISSUES: ValidationIssue[] = [];
const EMPTY_VALIDATION: ValidationContext = {
  issuesByNode: new Map(),
  lockedWorkflowIds: new Set(),
};

// TODO: Wire activeAgentIds to real session status when available
export function buildCanvasLayout(
  teams: Team[],
  agentsByTeam: Map<string, Agent[]>,
  workflows: Workflow[],
  workflowEdges: WorkflowEdge[],
  workflowColorMap: Map<string, string>,
  activeAgentIds: Set<string> = new Set(),
  callbacks: LayoutCallbacks = {},
  validation: ValidationContext = EMPTY_VALIDATION,
): LayoutResult {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  const startingAgentIds = new Set(workflows.map((wf) => wf.starting_agent_id));
  const agentsWithOutgoing = new Set(workflowEdges.map((e) => e.from_agent_id));

  let groupOffsetY = 0;

  for (const team of teams) {
    const agents = agentsByTeam.get(team.id) ?? [];
    // Grid columns = ceil(sqrt(N)) gives a roughly square layout (e.g. 4 agents → 2x2, 9 → 3x3)
    const columns = Math.max(Math.ceil(Math.sqrt(agents.length)), 1);

    const groupWidth = columns * (NODE_WIDTH + NODE_GAP_X) + GROUP_PADDING * 2 - NODE_GAP_X;
    const rows = Math.ceil(agents.length / columns);
    const groupHeight = rows * (NODE_HEIGHT + NODE_GAP_Y) + GROUP_HEADER_HEIGHT + GROUP_PADDING * 2 - NODE_GAP_Y;

    const groupId = `team-${team.id}`;
    const teamWorkflows = workflows.filter((w) => w.team_id === team.id);
    const isTeamLocked = teamWorkflows.some((w) =>
      validation.lockedWorkflowIds.has(w.id),
    );
    nodes.push({
      id: groupId,
      type: "teamGroup",
      position: { x: 0, y: groupOffsetY },
      data: {
        team,
        agentCount: agents.length,
        onAddAgent: callbacks.onAddAgent,
        onAddWorkflow: callbacks.onAddWorkflow,
        validationIssues: validation.issuesByNode.get(team.id) ?? EMPTY_ISSUES,
        isLocked: isTeamLocked,
      } satisfies TeamGroupNodeData,
      style: { width: groupWidth, height: groupHeight },
    });

    agents.forEach((agent, idx) => {
      const col = idx % columns;
      const row = Math.floor(idx / columns);

      const hasPosition = agent.position_x !== null && agent.position_y !== null;
      const x = hasPosition ? agent.position_x! : GROUP_PADDING + col * (NODE_WIDTH + NODE_GAP_X);
      const y = hasPosition ? agent.position_y! : GROUP_HEADER_HEIGHT + GROUP_PADDING + row * (NODE_HEIGHT + NODE_GAP_Y);

      const isStart = startingAgentIds.has(agent.id);
      const isEnd = !agentsWithOutgoing.has(agent.id) && workflowEdges.some((e) => e.to_agent_id === agent.id);
      const isActive = activeAgentIds.has(agent.id);

      nodes.push({
        id: `agent-${agent.id}`,
        type: "agentNode",
        position: { x, y },
        parentId: groupId,
        extent: "parent" as const,
        draggable: true,
        data: {
          agent,
          isStart,
          isEnd,
          isActive,
          validationIssues: validation.issuesByNode.get(agent.id) ?? EMPTY_ISSUES,
        } satisfies AgentNodeData,
        style: { width: NODE_WIDTH },
      });
    });

    groupOffsetY += groupHeight + GROUP_GAP;
  }

  for (const edge of workflowEdges) {
    const color = workflowColorMap.get(edge.workflow_id) ?? "#94a3b8";
    edges.push({
      id: `edge-${edge.id}`,
      source: `agent-${edge.from_agent_id}`,
      target: `agent-${edge.to_agent_id}`,
      type: "workflowEdge",
      data: {
        condition: edge.condition,
        requiresApproval: edge.requires_approval,
        color,
        edgeId: edge.id,
      },
      style: { stroke: color, strokeWidth: 2 },
      animated: false,
    });
  }

  return { nodes, edges };
}

export function buildWorkflowColorMap(workflows: Workflow[]): Map<string, string> {
  const map = new Map<string, string>();
  workflows.forEach((wf, i) => {
    map.set(wf.id, getWorkflowColor(i));
  });
  return map;
}

export function applyWorkflowFilter(
  edges: Edge[],
  selectedWorkflowId: string | null,
  workflowEdges: WorkflowEdge[],
  workflowColorMap: Map<string, string>,
): Edge[] {
  if (!selectedWorkflowId) return edges;

  const selectedEdgeIds = new Set(
    workflowEdges
      .filter((e) => e.workflow_id === selectedWorkflowId)
      .map((e) => `edge-${e.id}`),
  );

  return edges.map((edge) => {
    if (selectedEdgeIds.has(edge.id)) {
      const color = workflowColorMap.get(selectedWorkflowId) ?? "#94a3b8";
      return { ...edge, style: { ...edge.style, stroke: color, strokeWidth: 3, opacity: 1 } };
    }
    return { ...edge, style: { ...edge.style, stroke: "#d1d5db", strokeWidth: 1, opacity: 0.4 } };
  });
}
