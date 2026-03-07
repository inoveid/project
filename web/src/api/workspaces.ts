import { fetchApi } from "./client";

export interface Workspace {
  name: string;
  path: string;
}

export interface WorkspaceCreate {
  name: string;
  clone_url?: string;
}

export function getWorkspaces(): Promise<Workspace[]> {
  return fetchApi<Workspace[]>("/workspaces");
}

export function createWorkspace(data: WorkspaceCreate): Promise<Workspace> {
  return fetchApi<Workspace>("/workspaces", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
