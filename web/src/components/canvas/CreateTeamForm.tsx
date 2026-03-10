import { useState } from "react";
import type { TeamCreate } from "../../types";

interface CreateTeamFormProps {
  onSubmit: (data: TeamCreate) => void;
  onCancel: () => void;
}

export function CreateTeamForm({ onSubmit, onCancel }: CreateTeamFormProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSubmit({
      name: name.trim(),
      description: description.trim() || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <input
        type="text"
        placeholder="Team name *"
        className="border border-gray-300 rounded px-2 py-1 text-sm w-40"
        value={name}
        onChange={(e) => setName(e.target.value)}
        autoFocus
      />
      <input
        type="text"
        placeholder="Description"
        className="border border-gray-300 rounded px-2 py-1 text-sm w-48"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <button
        type="submit"
        disabled={!name.trim()}
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
    </form>
  );
}
