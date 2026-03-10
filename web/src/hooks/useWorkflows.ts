import { useQuery, useQueries } from "@tanstack/react-query";
import { getWorkflows, getWorkflow, getWorkflowEdges } from "../api/workflows";
import type { Workflow, WorkflowEdge } from "../types";

function workflowsKey(teamId: string) {
  return ["workflows", teamId] as const;
}

function workflowDetailKey(id: string) {
  return ["workflows", "detail", id] as const;
}

function workflowEdgesKey(workflowId: string) {
  return ["workflow-edges", workflowId] as const;
}

export function useWorkflows(teamId: string | null) {
  return useQuery({
    queryKey: workflowsKey(teamId ?? ""),
    queryFn: () => getWorkflows(teamId!),
    enabled: !!teamId,
  });
}

export function useWorkflow(id: string | null) {
  return useQuery({
    queryKey: workflowDetailKey(id ?? ""),
    queryFn: () => getWorkflow(id!),
    enabled: !!id,
  });
}

export function useWorkflowEdges(workflowId: string | null) {
  return useQuery({
    queryKey: workflowEdgesKey(workflowId ?? ""),
    queryFn: () => getWorkflowEdges(workflowId!),
    enabled: !!workflowId,
  });
}

export function useAllWorkflowEdges(workflows: Workflow[] | undefined) {
  const queries = useQueries({
    queries: (workflows ?? []).map((wf) => ({
      queryKey: workflowEdgesKey(wf.id),
      queryFn: () => getWorkflowEdges(wf.id),
    })),
  });

  const isLoading = queries.some((q) => q.isLoading);
  const allEdges: WorkflowEdge[] = [];
  for (const q of queries) {
    if (q.data) {
      allEdges.push(...q.data);
    }
  }

  return { data: allEdges, isLoading };
}
