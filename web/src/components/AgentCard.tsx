import type { Agent } from "../types";

interface AgentCardProps {
  agent: Agent;
  onEdit: (agent: Agent) => void;
  onDelete: (id: string) => void;
}

export function AgentCard({ agent, onEdit, onDelete }: AgentCardProps) {
  return (
    <div className="bg-white rounded-lg border p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{agent.name}</h3>
          <span className="text-sm text-blue-600">{agent.role}</span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onEdit(agent)}
            className="text-gray-400 hover:text-blue-500 text-sm"
          >
            Edit
          </button>
          <button
            onClick={() => onDelete(agent.id)}
            className="text-gray-400 hover:text-red-500 text-sm"
          >
            Delete
          </button>
        </div>
      </div>

      {agent.description && (
        <p className="mt-2 text-sm text-gray-600 line-clamp-2">
          {agent.description}
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-1">
        {agent.allowed_tools.map((tool) => (
          <span
            key={tool}
            className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded text-xs"
          >
            {tool}
          </span>
        ))}
      </div>

      <div className="mt-3">
        <button
          disabled
          className="text-sm text-gray-400 border border-gray-200 px-3 py-1 rounded cursor-not-allowed"
          title="Chat coming soon"
        >
          Chat
        </button>
      </div>
    </div>
  );
}
