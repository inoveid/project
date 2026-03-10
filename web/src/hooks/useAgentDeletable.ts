import { useQuery } from "@tanstack/react-query";
import { getAgentCanDelete } from "../api/agents";

interface AgentDeletableState {
  canDelete: boolean;
  reason: string | null;
  isLoading: boolean;
}

/**
 * Checks whether an agent can be safely deleted.
 *
 * Queries the backend which checks active sessions and workflow locks.
 */
export function useAgentDeletable(agentId: string | null): AgentDeletableState {
  const { data, isLoading } = useQuery({
    queryKey: ["agent-can-delete", agentId],
    queryFn: () => getAgentCanDelete(agentId!),
    enabled: agentId !== null,
    staleTime: 10_000,
  });

  if (!agentId) {
    return { canDelete: true, reason: null, isLoading: false };
  }

  return {
    canDelete: data?.can_delete ?? true,
    reason: data?.reason ?? null,
    isLoading,
  };
}
