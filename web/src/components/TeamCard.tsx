import { Link } from "react-router-dom";
import type { Team } from "../types";

interface TeamCardProps {
  team: Team;
  onEdit: (team: Team) => void;
  onDelete: (id: string) => void;
}

export function TeamCard({ team, onEdit, onDelete }: TeamCardProps) {
  return (
    <div className="bg-white rounded-lg border p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <Link
          to={`/teams/${team.id}`}
          className="text-lg font-semibold text-gray-900 hover:text-blue-600"
        >
          {team.name}
        </Link>
        <div className="flex gap-2">
          <button
            onClick={() => onEdit(team)}
            className="text-gray-400 hover:text-blue-500 text-sm"
            title="Edit team"
          >
            Edit
          </button>
          <button
            onClick={() => onDelete(team.id)}
            className="text-gray-400 hover:text-red-500 text-sm"
            title="Delete team"
          >
            Delete
          </button>
        </div>
      </div>
      {team.description && (
        <p className="mt-2 text-sm text-gray-600">{team.description}</p>
      )}
      <div className="mt-3 flex items-center gap-3 text-xs text-gray-500">
        <span>{team.agents_count} agent{team.agents_count !== 1 ? "s" : ""}</span>
        {team.project_scoped && (
          <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
            project-scoped
          </span>
        )}
      </div>
    </div>
  );
}
