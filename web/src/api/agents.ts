import type { Agent, AgentCreate, AgentUpdate } from "../types";
import { fetchApi } from "./client";

export function getAgents(teamId: string): Promise<Agent[]> {
  return fetchApi<Agent[]>(`/teams/${teamId}/agents`);
}

export function getAgent(id: string): Promise<Agent> {
  return fetchApi<Agent>(`/agents/${id}`);
}

export function createAgent(
  teamId: string,
  data: AgentCreate,
): Promise<Agent> {
  return fetchApi<Agent>(`/teams/${teamId}/agents`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateAgent(id: string, data: AgentUpdate): Promise<Agent> {
  return fetchApi<Agent>(`/agents/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteAgent(id: string): Promise<void> {
  return fetchApi<void>(`/agents/${id}`, { method: "DELETE" });
}
