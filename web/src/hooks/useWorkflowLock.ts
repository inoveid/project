import { useQuery } from "@tanstack/react-query";
import type { Task } from "../types";
import { getWorkflowActiveTasks, getWorkflowLockStatus } from "../api/workflows";

interface WorkflowLockState {
  isLocked: boolean;
  activeTasks: Task[];
  isLoading: boolean;
}

/**
 * Checks whether a workflow is locked due to active tasks (in_progress / awaiting_user).
 *
 * Polls every 30s so the UI stays up-to-date while the canvas is open.
 */
export function useWorkflowLock(workflowId: string | null): WorkflowLockState {
  const { data, isLoading } = useQuery({
    queryKey: ["workflow-active-tasks", workflowId],
    queryFn: () => getWorkflowActiveTasks(workflowId!),
    enabled: workflowId !== null,
    refetchInterval: 30_000,
    staleTime: 10_000,
  });

  if (!workflowId) {
    return { isLocked: false, activeTasks: [], isLoading: false };
  }

  return {
    isLocked: (data?.length ?? 0) > 0,
    activeTasks: data ?? [],
    isLoading,
  };
}

/**
 * Batch version: checks lock state for multiple workflows in a single HTTP request.
 *
 * Returns a Map<workflowId, boolean> indicating which are locked.
 */
export function useWorkflowLocks(workflowIds: string[]): Map<string, boolean> {
  const sortedIds = [...workflowIds].sort();
  const queries = useQuery({
    queryKey: ["workflow-locks", ...sortedIds],
    queryFn: async () => {
      const { locked_ids } = await getWorkflowLockStatus(workflowIds);
      const lockedSet = new Set(locked_ids);
      return new Map(workflowIds.map((id) => [id, lockedSet.has(id)]));
    },
    enabled: workflowIds.length > 0,
    refetchInterval: 30_000,
    staleTime: 10_000,
  });

  return queries.data ?? new Map();
}
