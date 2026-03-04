import type { AgentLink } from "../types";
import { fetchApi } from "./client";

export interface AgentLinkCreate {
  from_agent_id: string;
  to_agent_id: string;
  link_type: "handoff" | "review" | "migration_brief";
}

export function getAgentLinks(teamId: string): Promise<AgentLink[]> {
  return fetchApi<AgentLink[]>(`/teams/${teamId}/links`);
}

export function createAgentLink(
  teamId: string,
  data: AgentLinkCreate,
): Promise<AgentLink> {
  return fetchApi<AgentLink>(`/teams/${teamId}/links`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function deleteAgentLink(linkId: string): Promise<void> {
  return fetchApi<void>(`/links/${linkId}`, { method: "DELETE" });
}
