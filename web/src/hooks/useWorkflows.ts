import { useMutation, useQuery, useQueries, useQueryClient } from "@tanstack/react-query";
import {
  getWorkflows,
  getWorkflow,
  getWorkflowEdges,
  createWorkflow,
  updateWorkflow,
  deleteWorkflow,
  createWorkflowEdge,
  updateWorkflowEdge,
  deleteWorkflowEdge,
} from "../api/workflows";
import type {
  Workflow,
  WorkflowCreate,
  WorkflowUpdate,
  WorkflowEdge,
  WorkflowEdgeCreate,
  WorkflowEdgeUpdate,
} from "../types";

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

export function useCreateWorkflow(teamId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: WorkflowCreate) => createWorkflow(teamId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: workflowsKey(teamId) });
    },
  });
}

export function useUpdateWorkflow(teamId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WorkflowUpdate }) =>
      updateWorkflow(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: workflowsKey(teamId) });
    },
  });
}

export function useDeleteWorkflow(teamId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteWorkflow(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: workflowsKey(teamId) });
    },
  });
}

export function useCreateWorkflowEdge(workflowId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: WorkflowEdgeCreate) => createWorkflowEdge(workflowId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: workflowEdgesKey(workflowId) });
    },
  });
}

export function useUpdateWorkflowEdge(workflowId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WorkflowEdgeUpdate }) =>
      updateWorkflowEdge(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: workflowEdgesKey(workflowId) });
    },
  });
}

export function useDeleteWorkflowEdge(workflowId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteWorkflowEdge(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: workflowEdgesKey(workflowId) });
    },
  });
}
