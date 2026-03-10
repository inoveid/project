import { useState } from "react";
import type { Agent, WorkflowCreate } from "../../types";

interface CreateWorkflowFormProps {
  agents: Agent[];
  teamId: string;
  onSubmit: (teamId: string, data: WorkflowCreate) => void;
  onCancel: () => void;
}

export function CreateWorkflowForm({
  agents,
  teamId,
  onSubmit,
  onCancel,
}: CreateWorkflowFormProps) {
  const [name, setName] = useState("");
  const [startingAgentId, setStartingAgentId] = useState("");
  const [startingPrompt, setStartingPrompt] = useState("");

  const teamAgents = agents.filter((a) => a.team_id === teamId);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !startingAgentId || !startingPrompt.trim()) return;
    onSubmit(teamId, {
      name: name.trim(),
      starting_agent_id: startingAgentId,
      starting_prompt: startingPrompt.trim(),
    });
  };

  const isValid = name.trim() && startingAgentId && startingPrompt.trim();

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2 p-3 border border-gray-200 rounded bg-white">
      <h4 className="text-xs font-semibold text-gray-600">New workflow</h4>
      <input
        type="text"
        placeholder="Workflow name *"
        className="border border-gray-300 rounded px-2 py-1 text-sm"
        value={name}
        onChange={(e) => setName(e.target.value)}
        autoFocus
      />
      <select
        className="border border-gray-300 rounded px-2 py-1 text-sm"
        value={startingAgentId}
        onChange={(e) => setStartingAgentId(e.target.value)}
      >
        <option value="" disabled>Starting agent *</option>
        {teamAgents.map((a) => (
          <option key={a.id} value={a.id}>{a.name}</option>
        ))}
      </select>
      <textarea
        placeholder="Starting prompt *"
        className="border border-gray-300 rounded px-2 py-1 text-sm resize-y min-h-[60px]"
        value={startingPrompt}
        onChange={(e) => setStartingPrompt(e.target.value)}
      />
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!isValid}
          className="text-sm bg-blue-600 text-white rounded px-3 py-1 hover:bg-blue-700 disabled:opacity-50"
        >
          Create
        </button>
        <button
          type="button"
          className="text-sm text-gray-500 hover:text-gray-700"
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
