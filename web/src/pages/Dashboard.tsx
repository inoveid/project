import { useState } from "react";
import { CreateTeamForm } from "../components/CreateTeamForm";
import { TeamCard } from "../components/TeamCard";
import { useCreateTeam, useDeleteTeam, useTeams } from "../hooks/useTeams";

export function Dashboard() {
  const { data: teams, isLoading, error } = useTeams();
  const createTeam = useCreateTeam();
  const deleteTeam = useDeleteTeam();
  const [showForm, setShowForm] = useState(false);

  function handleDelete(id: string) {
    if (window.confirm("Delete this team?")) {
      deleteTeam.mutate(id);
    }
  }

  if (isLoading) {
    return <p className="text-gray-500">Loading teams...</p>;
  }

  if (error) {
    return <p className="text-red-600">Failed to load teams: {error.message}</p>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Teams</h1>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
          >
            Create Team
          </button>
        )}
      </div>

      {showForm && (
        <div className="mb-6">
          <CreateTeamForm
            onSubmit={(data) => {
              createTeam.mutate(data, {
                onSuccess: () => setShowForm(false),
              });
            }}
            onCancel={() => setShowForm(false)}
            isLoading={createTeam.isPending}
            error={createTeam.error?.message ?? null}
          />
        </div>
      )}

      {teams && teams.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {teams.map((team) => (
            <TeamCard key={team.id} team={team} onDelete={handleDelete} />
          ))}
        </div>
      ) : (
        <p className="text-gray-500">No teams yet. Create your first team to get started.</p>
      )}
    </div>
  );
}
