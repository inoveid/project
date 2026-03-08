import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ActiveSessions } from "../components/ActiveSessions";
import { QuickStartChat } from "../components/QuickStartChat";
import { SummaryCards } from "../components/SummaryCards";
import { TeamCard } from "../components/TeamCard";
import { TeamForm } from "../components/TeamForm";
import { WorkspacePanel } from "../components/WorkspacePanel";
import {
  useCreateTeam,
  useDeleteTeam,
  useTeams,
  useUpdateTeam,
} from "../hooks/useTeams";
import { useSessions } from "../hooks/useSessions";
import type { Team } from "../types";

type FormMode =
  | { kind: "closed" }
  | { kind: "create" }
  | { kind: "edit"; team: Team };

export function Dashboard() {
  const navigate = useNavigate();
  const { data: teams, isLoading, error } = useTeams();
  const { data: sessions } = useSessions();
  const createTeam = useCreateTeam();
  const updateTeam = useUpdateTeam();
  const deleteTeam = useDeleteTeam();
  const [formMode, setFormMode] = useState<FormMode>({ kind: "closed" });

  function handleDelete(id: string) {
    if (window.confirm("Delete this team?")) {
      deleteTeam.mutate(id, {
        onError: (err: Error) => alert(err.message),
      });
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

  const teamsCount = teams?.length ?? 0;
  const agentsCount = teams?.reduce((sum, t) => sum + t.agents_count, 0) ?? 0;
  const activeSessions = sessions ?? [];
  const activeMutation = formMode.kind === "create" ? createTeam : updateTeam;

  return (
    <div>
      <SummaryCards
        teamsCount={teamsCount}
        agentsCount={agentsCount}
        activeSessionsCount={activeSessions.length}
      />

      <section className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">
          Quick Start
        </h2>
        <QuickStartChat
          onSessionCreated={(id) => navigate(`/chat/${id}`)}
        />
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">
          Active Sessions
        </h2>
        <ActiveSessions
          sessions={activeSessions}
          onOpenChat={(id) => navigate(`/chat/${id}`)}
        />
      </section>

      <section className="mb-8">
        <WorkspacePanel />
      </section>

      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-gray-900">Teams</h2>
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
