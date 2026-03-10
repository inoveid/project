import type {
  Task,
  Workflow,
  WorkflowCreate,
  WorkflowUpdate,
  WorkflowEdge,
  WorkflowEdgeCreate,
  WorkflowEdgeUpdate,
} from "../types";
import { fetchApi } from "./client";

export function getWorkflows(teamId: string): Promise<Workflow[]> {
  return fetchApi<Workflow[]>(`/teams/${teamId}/workflows`);
}

export function getWorkflow(id: string): Promise<Workflow> {
  return fetchApi<Workflow>(`/workflows/${id}`);
}

export function createWorkflow(teamId: string, data: WorkflowCreate): Promise<Workflow> {
  return fetchApi<Workflow>(`/teams/${teamId}/workflows`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateWorkflow(id: string, data: WorkflowUpdate): Promise<Workflow> {
  return fetchApi<Workflow>(`/workflows/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteWorkflow(id: string): Promise<void> {
  return fetchApi<void>(`/workflows/${id}`, { method: "DELETE" });
}

export function getWorkflowEdges(workflowId: string): Promise<WorkflowEdge[]> {
  return fetchApi<WorkflowEdge[]>(`/workflows/${workflowId}/edges`);
}

export function createWorkflowEdge(
  workflowId: string,
  data: WorkflowEdgeCreate,
): Promise<WorkflowEdge> {
  return fetchApi<WorkflowEdge>(`/workflows/${workflowId}/edges`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateWorkflowEdge(
  id: string,
  data: WorkflowEdgeUpdate,
): Promise<WorkflowEdge> {
  return fetchApi<WorkflowEdge>(`/edges/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteWorkflowEdge(id: string): Promise<void> {
  return fetchApi<void>(`/edges/${id}`, { method: "DELETE" });
}

export function getWorkflowActiveTasks(workflowId: string): Promise<Task[]> {
  return fetchApi<Task[]>(`/workflows/${workflowId}/active-tasks`);
}

export function getWorkflowLockStatus(
  workflowIds: string[],
): Promise<{ locked_ids: string[] }> {
  return fetchApi<{ locked_ids: string[] }>("/workflows/lock-status", {
    method: "POST",
    body: JSON.stringify({ workflow_ids: workflowIds }),
  });
}
