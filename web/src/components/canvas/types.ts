import type { Agent, Team } from "../../types";

/**
 * ReactFlow types `data` as `Record<string, unknown>`, requiring a cast
 * to access typed fields. These interfaces use the index signature
 * `[key: string]: unknown` to satisfy xyflow's constraint.
 *
 * Use `getNodeData<T>(data)` for a single-point cast instead of
 * scattering `as` across every component.
 */

export interface AgentNodeData {
  agent: Agent;
  isStart: boolean;
  isEnd: boolean;
  isActive: boolean;
  [key: string]: unknown;
}

export interface TeamGroupNodeData {
  team: Team;
  agentCount: number;
  onAddAgent?: (teamId: string) => void;
  onAddWorkflow?: (teamId: string) => void;
  [key: string]: unknown;
}

export interface WorkflowEdgeData {
  condition: string | null;
  requiresApproval: boolean;
  color: string;
  edgeId: string;
  [key: string]: unknown;
}

/**
 * Single-point cast for ReactFlow node/edge data.
 * Centralizes the unavoidable `as` cast required by xyflow's typing.
 */
export function getNodeData<T>(data: Record<string, unknown>): T {
  return data as T;
}
