import type { Workflow, WorkflowEdge } from "../types";
import { fetchApi } from "./client";

export function getWorkflows(teamId: string): Promise<Workflow[]> {
  return fetchApi<Workflow[]>(`/teams/${teamId}/workflows`);
}

export function getWorkflow(id: string): Promise<Workflow> {
  return fetchApi<Workflow>(`/workflows/${id}`);
}

export function getWorkflowEdges(workflowId: string): Promise<WorkflowEdge[]> {
  return fetchApi<WorkflowEdge[]>(`/workflows/${workflowId}/edges`);
}
