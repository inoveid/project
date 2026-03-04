import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createTeam, deleteTeam, getTeam, getTeams, updateTeam } from "../api/teams";
import type { TeamCreate, TeamUpdate } from "../types";

const TEAMS_KEY = ["teams"] as const;

export function useTeams() {
  return useQuery({
    queryKey: TEAMS_KEY,
    queryFn: getTeams,
  });
}

export function useTeam(id: string) {
  return useQuery({
    queryKey: [...TEAMS_KEY, id],
    queryFn: () => getTeam(id),
    enabled: !!id,
  });
}

export function useCreateTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: TeamCreate) => createTeam(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: TEAMS_KEY });
    },
  });
}

export function useUpdateTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TeamUpdate }) =>
      updateTeam(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: TEAMS_KEY });
    },
  });
}

export function useDeleteTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteTeam(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: TEAMS_KEY });
    },
  });
}
