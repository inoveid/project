import type { Team, TeamCreate, TeamUpdate } from "../types";
import { fetchApi } from "./client";

export function getTeams(): Promise<Team[]> {
  return fetchApi<Team[]>("/teams");
}

export function getTeam(id: string): Promise<Team> {
  return fetchApi<Team>(`/teams/${id}`);
}

export function createTeam(data: TeamCreate): Promise<Team> {
  return fetchApi<Team>("/teams", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateTeam(id: string, data: TeamUpdate): Promise<Team> {
  return fetchApi<Team>(`/teams/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteTeam(id: string): Promise<void> {
  return fetchApi<void>(`/teams/${id}`, { method: "DELETE" });
}
