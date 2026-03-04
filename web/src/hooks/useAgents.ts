import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createAgent,
  deleteAgent,
  getAgents,
  updateAgent,
} from "../api/agents";
import type { AgentCreate, AgentUpdate } from "../types";

function agentsKey(teamId: string) {
  return ["teams", teamId, "agents"] as const;
}

export function useAgents(teamId: string) {
  return useQuery({
    queryKey: agentsKey(teamId),
    queryFn: () => getAgents(teamId),
    enabled: !!teamId,
  });
}

export function useCreateAgent(teamId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AgentCreate) => createAgent(teamId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: agentsKey(teamId) });
    },
  });
}

export function useUpdateAgent(teamId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AgentUpdate }) =>
      updateAgent(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: agentsKey(teamId) });
    },
  });
}

export function useDeleteAgent(teamId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteAgent(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: agentsKey(teamId) });
    },
  });
}
