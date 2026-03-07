import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createWorkspace, getWorkspaces } from "../api/workspaces";
import type { WorkspaceCreate } from "../api/workspaces";

const WORKSPACES_KEY = ["workspaces"] as const;

export function useWorkspaces() {
  return useQuery({
    queryKey: WORKSPACES_KEY,
    queryFn: getWorkspaces,
  });
}

export function useCreateWorkspace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: WorkspaceCreate) => createWorkspace(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: WORKSPACES_KEY });
    },
  });
}
