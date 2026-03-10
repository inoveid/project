import type { Session, SessionListItem } from "../types";
import { fetchApi } from "./client";

export function createSession(agentId: string): Promise<Session> {
  return fetchApi<Session>("/sessions", {
    method: "POST",
    body: JSON.stringify({ agent_id: agentId }),
  });
}

export function getSessions(): Promise<SessionListItem[]> {
  return fetchApi<SessionListItem[]>("/sessions");
}

export function getSessionsByTask(taskId: string): Promise<SessionListItem[]> {
  return fetchApi<SessionListItem[]>(`/sessions?task_id=${encodeURIComponent(taskId)}`);
}

export function getSession(sessionId: string): Promise<Session> {
  return fetchApi<Session>(`/sessions/${sessionId}`);
}

export function stopSession(sessionId: string): Promise<void> {
  return fetchApi<void>(`/sessions/${sessionId}`, { method: "DELETE" });
}
