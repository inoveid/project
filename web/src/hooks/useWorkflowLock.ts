import { useQuery } from "@tanstack/react-query";
import type { Task } from "../types";
import { getWorkflowActiveTasks } from "../api/workflows";

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
 * Batch version: checks lock state for multiple workflows at once.
 *
 * Returns a Map<workflowId, boolean> indicating which are locked.
 */
export function useWorkflowLocks(workflowIds: string[]): Map<string, boolean> {
  const queries = useQuery({
    queryKey: ["workflow-locks", ...workflowIds.sort()],
    queryFn: async () => {
      const results = await Promise.all(
        workflowIds.map(async (id) => {
          const tasks = await getWorkflowActiveTasks(id);
          return [id, tasks.length > 0] as const;
        }),
      );
      return new Map(results);
    },
    enabled: workflowIds.length > 0,
    refetchInterval: 30_000,
    staleTime: 10_000,
  });

  return queries.data ?? new Map();
}
