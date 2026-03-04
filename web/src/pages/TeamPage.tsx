import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AgentCard } from "../components/AgentCard";
import { AgentForm } from "../components/AgentForm";
import {
  useAgents,
  useCreateAgent,
  useDeleteAgent,
  useUpdateAgent,
} from "../hooks/useAgents";
import { useTeam } from "../hooks/useTeams";
import type { Agent, AgentCreate, AgentUpdate } from "../types";

type FormMode = { kind: "closed" } | { kind: "create" } | { kind: "edit"; agent: Agent };

export function TeamPage() {
  const { id } = useParams<{ id: string }>();
  const teamId = id ?? "";
  const { data: team, isLoading: teamLoading } = useTeam(teamId);
  const { data: agents, isLoading: agentsLoading } = useAgents(teamId);
  const createAgent = useCreateAgent(teamId);
  const updateAgent = useUpdateAgent(teamId);
  const deleteAgent = useDeleteAgent(teamId);
  const [formMode, setFormMode] = useState<FormMode>({ kind: "closed" });

  function handleDelete(agentId: string) {
    if (window.confirm("Delete this agent?")) {
      deleteAgent.mutate(agentId);
    }
  }

  function handleEdit(agent: Agent) {
    setFormMode({ kind: "edit", agent });
  }

  function handleCreate(data: AgentCreate) {
    createAgent.mutate(data, {
      onSuccess: () => setFormMode({ kind: "closed" }),
    });
  }

  function handleUpdate(data: AgentUpdate) {
    if (formMode.kind !== "edit") return;
    updateAgent.mutate(
      { id: formMode.agent.id, data },
      { onSuccess: () => setFormMode({ kind: "closed" }) },
    );
  }

  if (teamLoading || agentsLoading) {
    return <p className="text-gray-500">Loading...</p>;
  }

  if (!team) {
    return <p className="text-red-600">Team not found.</p>;
  }

  const activeMutation = formMode.kind === "create" ? createAgent : updateAgent;

  return (
    <div>
      <div className="mb-1">
        <Link to="/" className="text-sm text-blue-600 hover:underline">
          &larr; Teams
        </Link>
      </div>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{team.name}</h1>
          {team.description && (
            <p className="text-sm text-gray-500 mt-1">{team.description}</p>
          )}
        </div>
        {formMode.kind === "closed" && (
          <button
            onClick={() => setFormMode({ kind: "create" })}
            className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
          >
            Add Agent
          </button>
        )}
      </div>

      {formMode.kind !== "closed" && (
        <div className="mb-6">
          <AgentForm
            initial={formMode.kind === "edit" ? formMode.agent : undefined}
            onCreate={handleCreate}
            onUpdate={handleUpdate}
            onCancel={() => setFormMode({ kind: "closed" })}
            isLoading={activeMutation.isPending}
            error={activeMutation.error?.message ?? null}
          />
        </div>
      )}

      {agents && agents.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          ))}
        </div>
      ) : (
        <p className="text-gray-500">
          No agents yet. Add your first agent to this team.
        </p>
      )}
    </div>
  );
}
