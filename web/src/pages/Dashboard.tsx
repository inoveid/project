import { useState } from "react";
import { TeamCard } from "../components/TeamCard";
import { TeamForm } from "../components/TeamForm";
import { SessionList } from "../components/SessionList";
import {
  useCreateTeam,
  useDeleteTeam,
  useTeams,
  useUpdateTeam,
} from "../hooks/useTeams";
import type { Team } from "../types";

type FormMode =
  | { kind: "closed" }
  | { kind: "create" }
  | { kind: "edit"; team: Team };

export function Dashboard() {
  const { data: teams, isLoading, error } = useTeams();
  const createTeam = useCreateTeam();
  const updateTeam = useUpdateTeam();
  const deleteTeam = useDeleteTeam();
  const [formMode, setFormMode] = useState<FormMode>({ kind: "closed" });

  function handleDelete(id: string) {
    if (window.confirm("Delete this team?")) {
      deleteTeam.mutate(id);
    }
  }

  function handleEdit(team: Team) {
    setFormMode({ kind: "edit", team });
  }

  if (isLoading) {
    return <p className="text-gray-500">Loading teams...</p>;
  }

  if (error) {
    return (
      <p className="text-red-600">Failed to load teams: {error.message}</p>
    );
  }

  const activeMutation = formMode.kind === "create" ? createTeam : updateTeam;

  return (
    <div>
      <SessionList />

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Teams</h1>
        {formMode.kind === "closed" && (
          <button
            onClick={() => setFormMode({ kind: "create" })}
            className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
          >
            Create Team
          </button>
        )}
      </div>

      {formMode.kind !== "closed" && (
        <div className="mb-6">
          <TeamForm
            initial={formMode.kind === "edit" ? formMode.team : undefined}
            onCreate={(data) => {
              createTeam.mutate(data, {
                onSuccess: () => setFormMode({ kind: "closed" }),
              });
            }}
            onUpdate={(data) => {
              if (formMode.kind !== "edit") return;
              updateTeam.mutate(
                { id: formMode.team.id, data },
                { onSuccess: () => setFormMode({ kind: "closed" }) },
              );
            }}
            onCancel={() => setFormMode({ kind: "closed" })}
            isLoading={activeMutation.isPending}
            error={activeMutation.error?.message ?? null}
          />
        </div>
      )}

      {teams && teams.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {teams.map((team) => (
            <TeamCard
              key={team.id}
              team={team}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          ))}
        </div>
      ) : (
        <p className="text-gray-500">
          No teams yet. Create your first team to get started.
        </p>
      )}
    </div>
  );
}
