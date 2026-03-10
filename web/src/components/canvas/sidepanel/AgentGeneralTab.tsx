import { useState } from "react";
import type { Agent, AgentUpdate } from "../../../types";
import { useAutoSave } from "../../../hooks/useAutoSave";
import { useAgentDeletable } from "../../../hooks/useAgentDeletable";
import { useToast } from "../../../hooks/useToast";

interface AgentGeneralTabProps {
  agent: Agent;
  onSave: (data: AgentUpdate) => void;
  onDelete: () => void;
}

export function AgentGeneralTab({ agent, onSave, onDelete }: AgentGeneralTabProps) {
  const { addToast } = useToast();
  const [name, setName] = useState(agent.name);
  const [description, setDescription] = useState(agent.description ?? "");
  const [systemPrompt, setSystemPrompt] = useState(agent.system_prompt);
  const [allowedTools, setAllowedTools] = useState(agent.allowed_tools.join(", "));
  const [maxCycles, setMaxCycles] = useState(agent.max_cycles);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { canDelete, reason: deleteBlockReason } = useAgentDeletable(agent.id);

  const saveField = (field: keyof AgentUpdate, value: unknown) => {
    onSave({ [field]: value });
  };

  const { flush: flushTools } = useAutoSave(() => {
    const tools = allowedTools
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    saveField("allowed_tools", tools);
  }, 500);

  const handleDeleteClick = () => {
    if (!canDelete) {
      addToast({
        type: "warning",
        title: "Удаление заблокировано",
        message: deleteBlockReason ?? "Cannot delete this agent",
      });
      return;
    }
    setShowDeleteConfirm(true);
  };

  return (
    <div className="flex flex-col gap-4">
      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-gray-600">Name</span>
        <input
          type="text"
          className="border border-gray-200 rounded px-2 py-1.5 text-sm"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={() => {
            if (name !== agent.name) saveField("name", name);
          }}
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-gray-600">Description</span>
        <textarea
          className="border border-gray-200 rounded px-2 py-1.5 text-sm resize-y min-h-[60px]"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          onBlur={() => {
            const val = description || null;
            if (val !== agent.description) saveField("description", val);
          }}
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-gray-600">System Prompt</span>
        <textarea
          className="border border-gray-200 rounded px-2 py-1.5 text-sm resize-y min-h-[120px] font-mono text-xs"
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
          onBlur={() => {
            if (systemPrompt !== agent.system_prompt) saveField("system_prompt", systemPrompt);
          }}
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-gray-600">Allowed Tools (comma-separated)</span>
        <input
          type="text"
          className="border border-gray-200 rounded px-2 py-1.5 text-sm"
          value={allowedTools}
          onChange={(e) => {
            setAllowedTools(e.target.value);
          }}
          onBlur={flushTools}
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-gray-600">Max Cycles</span>
        <input
          type="number"
          className="border border-gray-200 rounded px-2 py-1.5 text-sm w-24"
          value={maxCycles}
          min={1}
          onChange={(e) => {
            const val = parseInt(e.target.value, 10);
            if (!isNaN(val) && val > 0) {
              setMaxCycles(val);
            }
          }}
          onBlur={() => {
            if (maxCycles !== agent.max_cycles) saveField("max_cycles", maxCycles);
          }}
        />
      </label>

      <div className="pt-4 border-t border-gray-100">
        {!canDelete && deleteBlockReason && (
          <p className="text-xs text-amber-600 mb-2" data-testid="delete-block-reason">
            {deleteBlockReason}
          </p>
        )}
        {!showDeleteConfirm ? (
          <button
            type="button"
            className={`text-sm ${canDelete ? "text-red-600 hover:text-red-700" : "text-gray-400 cursor-not-allowed"}`}
            onClick={handleDeleteClick}
            disabled={!canDelete}
          >
            Delete agent
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-sm text-red-600">Are you sure?</span>
            <button
              type="button"
              className="text-sm bg-red-600 text-white rounded px-3 py-1 hover:bg-red-700"
              onClick={onDelete}
            >
              Delete
            </button>
            <button
              type="button"
              className="text-sm text-gray-500 hover:text-gray-700"
              onClick={() => setShowDeleteConfirm(false)}
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
