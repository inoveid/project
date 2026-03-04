import { useState } from "react";
import type { Team, TeamCreate, TeamUpdate } from "../types";

interface TeamFormProps {
  initial?: Team;
  onCreate?: (data: TeamCreate) => void;
  onUpdate?: (data: TeamUpdate) => void;
  onCancel: () => void;
  isLoading: boolean;
  error: string | null;
}

export function TeamForm({
  initial,
  onCreate,
  onUpdate,
  onCancel,
  isLoading,
  error,
}: TeamFormProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [projectScoped, setProjectScoped] = useState(
    initial?.project_scoped ?? false,
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;

    if (initial && onUpdate) {
      const update: TeamUpdate = {};
      if (name.trim() !== initial.name) update.name = name.trim();
      if ((description.trim() || null) !== initial.description)
        update.description = description.trim() || null;
      if (projectScoped !== initial.project_scoped)
        update.project_scoped = projectScoped;
      onUpdate(update);
    } else if (onCreate) {
      onCreate({
        name: name.trim(),
        description: description.trim() || undefined,
        project_scoped: projectScoped,
      });
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-lg border p-5 space-y-4"
    >
      <h3 className="text-lg font-semibold text-gray-900">
        {initial ? "Edit Team" : "Create Team"}
      </h3>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 rounded p-2">{error}</p>
      )}

      <div>
        <label
          htmlFor="team-name"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Name *
        </label>
        <input
          id="team-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm"
          required
          maxLength={100}
          autoFocus
        />
      </div>

      <div>
        <label
          htmlFor="team-desc"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Description
        </label>
        <textarea
          id="team-desc"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm"
          rows={3}
        />
      </div>

      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={projectScoped}
          onChange={(e) => setProjectScoped(e.target.checked)}
        />
        Project scoped
      </label>

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={isLoading || !name.trim()}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {isLoading ? "Saving..." : initial ? "Save" : "Create"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="border px-4 py-2 rounded text-sm hover:bg-gray-50"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
