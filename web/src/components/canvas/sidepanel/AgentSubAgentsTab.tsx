import { useState } from "react";
import type { Agent, AgentUpdate, SubAgentTemplate } from "../../../types";

interface AgentSubAgentsTabProps {
  agent: Agent;
  onSave: (data: AgentUpdate) => void;
}

function generateId(): string {
  return crypto.randomUUID().slice(0, 8);
}

const DEFAULT_TEMPLATE: Omit<SubAgentTemplate, "id"> = {
  role: "",
  name: "",
  system_prompt: "",
  allowed_tools: [],
  max_budget_usd: 0.5,
  description: "",
};

export function AgentSubAgentsTab({ agent, onSave }: AgentSubAgentsTabProps) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editData, setEditData] = useState<SubAgentTemplate>({
    id: "",
    ...DEFAULT_TEMPLATE,
  });

  const templates: SubAgentTemplate[] = agent.sub_agent_templates ?? [];

  const startEdit = (index: number) => {
    const t = templates[index];
    if (!t) return;
    setEditingIndex(index);
    setEditData({ ...t });
  };

  const startCreate = () => {
    setEditingIndex(-1);
    setEditData({ id: generateId(), ...DEFAULT_TEMPLATE });
  };

  const cancelEdit = () => {
    setEditingIndex(null);
  };

  const saveEdit = () => {
    if (!editData.role.trim() || !editData.name.trim() || !editData.system_prompt.trim()) return;

    const updated = [...templates];
    if (editingIndex === -1) {
      updated.push(editData);
    } else if (editingIndex !== null) {
      updated[editingIndex] = editData;
    }

    onSave({ sub_agent_templates: updated });
    cancelEdit();
  };

  const deleteTemplate = (index: number) => {
    const updated = templates.filter((_, i) => i !== index);
    onSave({ sub_agent_templates: updated });
  };

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-gray-500">
        Sub-agents are helpers this agent can spawn to perform specific tasks.
        The agent will see these as available roles to delegate work to.
      </p>

      {templates.map((t, idx) => (
        <div
          key={t.id}
          className="border border-gray-200 rounded p-3"
        >
          {editingIndex === idx ? (
            <TemplateEditor
              data={editData}
              onChange={setEditData}
              onSave={saveEdit}
              onCancel={cancelEdit}
            />
          ) : (
            <div className="flex flex-col gap-1">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium text-gray-800">{t.name}</span>
                  <span className="text-xs text-gray-400 ml-2">({t.role})</span>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="text-xs text-blue-600 hover:text-blue-700"
                    onClick={() => startEdit(idx)}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="text-xs text-red-600 hover:text-red-700"
                    onClick={() => deleteTemplate(idx)}
                  >
                    Delete
                  </button>
                </div>
              </div>
              {t.description && (
                <p className="text-xs text-gray-500">{t.description}</p>
              )}
              <div className="flex gap-3 text-xs text-gray-400">
                <span>Budget: ${t.max_budget_usd}</span>
                {t.allowed_tools.length > 0 && (
                  <span>Tools: {t.allowed_tools.length}</span>
                )}
              </div>
            </div>
          )}
        </div>
      ))}

      {editingIndex === -1 ? (
        <div className="border border-gray-200 rounded p-3">
          <TemplateEditor
            data={editData}
            onChange={setEditData}
            onSave={saveEdit}
            onCancel={cancelEdit}
          />
        </div>
      ) : (
        <button
          type="button"
          className="text-sm text-blue-600 hover:text-blue-700 text-left"
          onClick={startCreate}
        >
          + Add sub-agent template
        </button>
      )}

      {templates.length === 0 && editingIndex === null && (
        <p className="text-xs text-gray-400">No sub-agent templates yet</p>
      )}

      <div className="pt-4 border-t border-gray-100">
        <h3 className="text-xs font-medium text-gray-600 mb-2">Settings</h3>
        <label className="flex items-center gap-2">
          <span className="text-xs text-gray-600">Max concurrent sub-agents</span>
          <input
            type="number"
            min="1"
            max="10"
            className="border border-gray-200 rounded px-2 py-1 text-sm w-16"
            value={(agent.config as Record<string, unknown>)?.max_sub_agents as number ?? 3}
            onChange={(e) => {
              const val = parseInt(e.target.value) || 3;
              onSave({ config: { ...agent.config, max_sub_agents: Math.min(Math.max(val, 1), 10) } });
            }}
          />
        </label>
        <p className="text-xs text-gray-400 mt-1">
          How many sub-agents can run in parallel. Also applies to custom sub-agents.
        </p>
      </div>
    </div>
  );
}

function TemplateEditor({
  data,
  onChange,
  onSave,
  onCancel,
}: {
  data: SubAgentTemplate;
  onChange: (d: SubAgentTemplate) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  const [toolsStr, setToolsStr] = useState(data.allowed_tools.join(", "));

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Role (e.g. researcher)"
          className="border border-gray-200 rounded px-2 py-1 text-sm flex-1"
          value={data.role}
          onChange={(e) => onChange({ ...data, role: e.target.value })}
        />
        <input
          type="text"
          placeholder="Display name"
          className="border border-gray-200 rounded px-2 py-1 text-sm flex-1"
          value={data.name}
          onChange={(e) => onChange({ ...data, name: e.target.value })}
        />
      </div>

      <input
        type="text"
        placeholder="Short description"
        className="border border-gray-200 rounded px-2 py-1 text-sm"
        value={data.description}
        onChange={(e) => onChange({ ...data, description: e.target.value })}
      />

      <textarea
        placeholder="System prompt for this sub-agent"
        className="border border-gray-200 rounded px-2 py-1 text-sm resize-y min-h-[80px] font-mono text-xs"
        value={data.system_prompt}
        onChange={(e) => onChange({ ...data, system_prompt: e.target.value })}
      />

      <input
        type="text"
        placeholder="Allowed tools (comma-separated)"
        className="border border-gray-200 rounded px-2 py-1 text-sm"
        value={toolsStr}
        onChange={(e) => {
          setToolsStr(e.target.value);
          const tools = e.target.value.split(",").map((t) => t.trim()).filter(Boolean);
          onChange({ ...data, allowed_tools: tools });
        }}
      />

      <div className="flex items-center gap-2">
        <label className="text-xs text-gray-600">Budget per spawn ($)</label>
        <input
          type="number"
          step="0.1"
          min="0"
          className="border border-gray-200 rounded px-2 py-1 text-sm w-20"
          value={data.max_budget_usd}
          onChange={(e) =>
            onChange({ ...data, max_budget_usd: parseFloat(e.target.value) || 0 })
          }
        />
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          className="text-xs bg-blue-600 text-white rounded px-3 py-1 hover:bg-blue-700"
          onClick={onSave}
        >
          Save
        </button>
        <button
          type="button"
          className="text-xs text-gray-500 hover:text-gray-700"
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
