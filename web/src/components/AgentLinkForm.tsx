import { useState } from "react";
import type { Agent } from "../types";
import type { AgentLinkCreate } from "../api/agentLinks";

const LINK_TYPES = ["handoff", "review", "migration_brief"] as const;

interface AgentLinkFormProps {
  agents: Agent[];
  onSubmit: (data: AgentLinkCreate) => void;
  onCancel: () => void;
  isLoading: boolean;
  error: string | null;
}

export function AgentLinkForm({
  agents,
  onSubmit,
  onCancel,
  isLoading,
  error,
}: AgentLinkFormProps) {
  const [fromAgentId, setFromAgentId] = useState("");
  const [toAgentId, setToAgentId] = useState("");
  const [linkType, setLinkType] = useState<(typeof LINK_TYPES)[number]>("handoff");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!fromAgentId || !toAgentId) return;
    onSubmit({
      from_agent_id: fromAgentId,
      to_agent_id: toAgentId,
      link_type: linkType,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white border rounded-lg p-4 space-y-3">
      <h3 className="font-semibold text-gray-900">New Link</h3>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-sm text-gray-600 mb-1">From</label>
          <select
            value={fromAgentId}
            onChange={(e) => setFromAgentId(e.target.value)}
            className="w-full border rounded px-2 py-1.5 text-sm"
            required
          >
            <option value="">Select agent</option>
            {agents.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm text-gray-600 mb-1">To</label>
          <select
            value={toAgentId}
            onChange={(e) => setToAgentId(e.target.value)}
            className="w-full border rounded px-2 py-1.5 text-sm"
            required
          >
            <option value="">Select agent</option>
            {agents.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm text-gray-600 mb-1">Type</label>
          <select
            value={linkType}
            onChange={(e) => setLinkType(e.target.value as (typeof LINK_TYPES)[number])}
            className="w-full border rounded px-2 py-1.5 text-sm"
          >
            {LINK_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={isLoading || !fromAgentId || !toAgentId}
          className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {isLoading ? "Creating..." : "Create Link"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="border px-4 py-1.5 rounded text-sm hover:bg-gray-50"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
