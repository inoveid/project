import { useState } from "react";
import type { Team, TeamUpdate } from "../../../types";

interface TeamPanelProps {
  team: Team;
  onSave: (data: TeamUpdate) => void;
  onDelete?: () => void;
}

export function TeamPanel({ team, onSave }: TeamPanelProps) {
  const [name, setName] = useState(team.name);
  const [description, setDescription] = useState(team.description ?? "");

  return (
    <div className="flex flex-col gap-4">
      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-gray-600">Название</span>
        <input
          type="text"
          className="border border-gray-200 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={() => {
            const val = name.trim();
            if (val && val !== team.name) onSave({ name: val });
          }}
          maxLength={100}
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-gray-600">Описание</span>
        <textarea
          className="border border-gray-200 rounded px-2.5 py-1.5 text-sm resize-y min-h-[80px] focus:outline-none focus:ring-2 focus:ring-blue-400"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          onBlur={() => {
            const val = description.trim() || null;
            if (val !== team.description) onSave({ description: val });
          }}
          placeholder="Описание команды..."
        />
      </label>

      <div className="flex items-center gap-2 text-sm text-gray-500">
        <span>Агентов: {team.agents_count}</span>
        <span>·</span>
        <span>Создана: {new Date(team.created_at).toLocaleDateString("ru")}</span>
      </div>

    </div>
  );
}
