import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createAgentLink,
  deleteAgentLink,
  getAgentLinks,
} from "../api/agentLinks";
import type { AgentLinkCreate } from "../api/agentLinks";

function linksKey(teamId: string) {
  return ["teams", teamId, "links"] as const;
}

export function useAgentLinks(teamId: string) {
  return useQuery({
    queryKey: linksKey(teamId),
    queryFn: () => getAgentLinks(teamId),
    enabled: !!teamId,
  });
}

export function useCreateAgentLink(teamId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AgentLinkCreate) => createAgentLink(teamId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: linksKey(teamId) });
    },
  });
}

export function useDeleteAgentLink(teamId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (linkId: string) => deleteAgentLink(linkId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: linksKey(teamId) });
    },
  });
}
