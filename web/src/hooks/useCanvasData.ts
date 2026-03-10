import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import { getWorkflows } from "../api/workflows";
import { useAllWorkflowEdges } from "./useWorkflows";
import type { Team, Workflow } from "../types";

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

  const { data: allEdges, isLoading: edgesLoading } = useAllWorkflowEdges(allWorkflows);

  const isLoading =
    workflowQueries.some((q) => q.isLoading) || edgesLoading;

  return { allWorkflows, allEdges, isLoading };
}
