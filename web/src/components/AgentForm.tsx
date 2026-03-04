import { useState } from "react";
import type { Agent, AgentCreate, AgentUpdate } from "../types";

interface AgentFormProps {
  initial?: Agent;
  onSubmit: (data: AgentCreate | AgentUpdate) => void;
  onCancel: () => void;
  isLoading: boolean;
  error: string | null;
}

export function AgentForm({
  initial,
  onSubmit,
  onCancel,
  isLoading,
  error,
}: AgentFormProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [role, setRole] = useState(initial?.role ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [systemPrompt, setSystemPrompt] = useState(
    initial?.system_prompt ?? "",
  );
  const [allowedTools, setAllowedTools] = useState(
    initial?.allowed_tools.join(", ") ?? "",
  );
  const [configJson, setConfigJson] = useState(
    initial ? JSON.stringify(initial.config, null, 2) : "{}",
  );
  const [configError, setConfigError] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setConfigError(null);

    let parsedConfig: Record<string, unknown>;
    try {
      parsedConfig = JSON.parse(configJson) as Record<string, unknown>;
    } catch {
      setConfigError("Invalid JSON");
      return;
    }

    const tools = allowedTools
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

    if (initial) {
      const update: AgentUpdate = {};
      if (name !== initial.name) update.name = name;
      if (role !== initial.role) update.role = role;
      if (description !== (initial.description ?? ""))
        update.description = description || null;
      if (systemPrompt !== initial.system_prompt)
        update.system_prompt = systemPrompt;
      if (allowedTools !== initial.allowed_tools.join(", "))
        update.allowed_tools = tools;
      if (configJson !== JSON.stringify(initial.config, null, 2))
        update.config = parsedConfig;
      onSubmit(update);
    } else {
      onSubmit({
        name,
        role,
        description: description || null,
        system_prompt: systemPrompt,
        allowed_tools: tools,
        config: parsedConfig,
      });
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg border p-5">
      <h3 className="text-lg font-semibold mb-4">
        {initial ? "Edit Agent" : "Create Agent"}
      </h3>

      {error && <p className="text-red-600 text-sm mb-3">{error}</p>}

      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={100}
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="e.g. Coder"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Role
            </label>
            <input
              type="text"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              required
              maxLength={100}
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="e.g. developer"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Description
          </label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm"
            placeholder="Brief description of the agent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            System Prompt
          </label>
          <textarea
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            required
            rows={5}
            className="w-full border rounded px-3 py-2 text-sm font-mono"
            placeholder="Instructions for the agent..."
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Allowed Tools (comma-separated)
          </label>
          <input
            type="text"
            value={allowedTools}
            onChange={(e) => setAllowedTools(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm"
            placeholder="bash, read, write"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Config (JSON)
          </label>
          <textarea
            value={configJson}
            onChange={(e) => setConfigJson(e.target.value)}
            rows={3}
            className="w-full border rounded px-3 py-2 text-sm font-mono"
          />
          {configError && (
            <p className="text-red-600 text-xs mt-1">{configError}</p>
          )}
        </div>
      </div>

      <div className="mt-4 flex gap-2">
        <button
          type="submit"
          disabled={isLoading}
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
