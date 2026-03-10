import { useState } from "react";
import type { WorkflowEdge, WorkflowEdgeUpdate, AgentPrompt } from "../../../types";

interface EdgePanelProps {
  edge: WorkflowEdge;
  toAgentPrompts: AgentPrompt[];
  onSave: (data: WorkflowEdgeUpdate) => void;
  onDelete: () => void;
}

export function EdgePanel({ edge, toAgentPrompts, onSave, onDelete }: EdgePanelProps) {
  const [condition, setCondition] = useState(edge.condition ?? "");
  const [promptTemplate, setPromptTemplate] = useState(edge.prompt_template ?? "");
  const [requiresApproval, setRequiresApproval] = useState(edge.requires_approval);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  return (
    <div className="flex flex-col gap-4">
      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-gray-600">Condition</span>
        <textarea
          className="border border-gray-200 rounded px-2 py-1.5 text-sm resize-y min-h-[60px]"
          value={condition}
          onChange={(e) => setCondition(e.target.value)}
          onBlur={() => {
            const val = condition || null;
            if (val !== edge.condition) onSave({ condition: val });
          }}
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-gray-600">Prompt template</span>
        <textarea
          className="border border-gray-200 rounded px-2 py-1.5 text-sm resize-y min-h-[80px] font-mono text-xs"
          value={promptTemplate}
          onChange={(e) => setPromptTemplate(e.target.value)}
          onBlur={() => {
            const val = promptTemplate || null;
            if (val !== edge.prompt_template) onSave({ prompt_template: val });
          }}
        />
      </label>

      {toAgentPrompts.length > 0 && (
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">Prompt (from target agent)</span>
          <select
            className="border border-gray-200 rounded px-2 py-1.5 text-sm"
            value={edge.prompt_id ?? ""}
            onChange={(e) => {
              const val = e.target.value || null;
              onSave({ prompt_id: val });
            }}
          >
            <option value="">None</option>
            {toAgentPrompts.map((p, idx) => (
              <option key={`${p.name}-${idx}`} value={p.name}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      )}

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={requiresApproval}
          onChange={(e) => {
            setRequiresApproval(e.target.checked);
            onSave({ requires_approval: e.target.checked });
          }}
        />
        <span className="text-sm text-gray-700">Requires approval</span>
      </label>

      <div className="pt-4 border-t border-gray-100">
        {!showDeleteConfirm ? (
          <button
            type="button"
            className="text-sm text-red-600 hover:text-red-700"
            onClick={() => setShowDeleteConfirm(true)}
          >
            Delete edge
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
