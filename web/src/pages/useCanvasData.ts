import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import { getWorkflows, getWorkflowEdges } from "../api/workflows";
import type { Team, Workflow, WorkflowEdge } from "../types";

export function useCanvasData(teams: Team[] | undefined) {
  const teamIds = useMemo(() => (teams ?? []).map((t) => t.id), [teams]);

  const workflowQueries = useQueries({
    queries: teamIds.map((teamId) => ({
      queryKey: ["workflows", teamId] as const,
      queryFn: () => getWorkflows(teamId),
      enabled: teamIds.length > 0,
    })),
  });

  const allWorkflows = useMemo(() => {
    const result: Workflow[] = [];
    for (const q of workflowQueries) {
      if (q.data) result.push(...q.data);
    }
    return result;
  }, [workflowQueries]);

  const workflowIds = useMemo(() => allWorkflows.map((wf) => wf.id), [allWorkflows]);

  const edgeQueries = useQueries({
    queries: workflowIds.map((wfId) => ({
      queryKey: ["workflow-edges", wfId] as const,
      queryFn: () => getWorkflowEdges(wfId),
      enabled: workflowIds.length > 0,
    })),
  });

  const allEdges = useMemo(() => {
    const result: WorkflowEdge[] = [];
    for (const q of edgeQueries) {
      if (q.data) result.push(...q.data);
    }
    return result;
  }, [edgeQueries]);

  const isLoading =
    workflowQueries.some((q) => q.isLoading) ||
    edgeQueries.some((q) => q.isLoading);

  return { allWorkflows, allEdges, isLoading };
}
