import { useState } from "react";
import type { WorkflowEdge, WorkflowEdgeUpdate, AgentPrompt } from "../../../types";

interface EdgePanelProps {
  edge: WorkflowEdge;
  toAgentPrompts: AgentPrompt[];
  onSave: (data: WorkflowEdgeUpdate) => void;
  onDelete: () => void;
  readOnly?: boolean;
}

export function EdgePanel({ edge, toAgentPrompts, onSave, onDelete, readOnly }: EdgePanelProps) {
  const [condition, setCondition] = useState(edge.condition ?? "");
  const [promptTemplate, setPromptTemplate] = useState(edge.prompt_template ?? "");
  const [requiresApproval, setRequiresApproval] = useState(edge.requires_approval);
  const [maxRounds, setMaxRounds] = useState(edge.max_rounds ?? 3);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const disabledClass = readOnly ? "opacity-60 pointer-events-none" : "";

  return (
    <div className="flex flex-col gap-4">
      {readOnly && (
        <div
          className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1.5"
          data-testid="edge-locked-notice"
        >
          Workflow is being used by an active task. Editing is disabled.
        </div>
      )}

      <label className={`flex flex-col gap-1 ${disabledClass}`}>
        <span className="text-xs font-medium text-gray-600">Condition</span>
        <textarea
          className="border border-gray-200 rounded px-2 py-1.5 text-sm resize-y min-h-[60px]"
          value={condition}
          onChange={(e) => setCondition(e.target.value)}
          onBlur={() => {
            const val = condition || null;
            if (val !== edge.condition) onSave({ condition: val });
          }}
          disabled={readOnly}
        />
      </label>

      <label className={`flex flex-col gap-1 ${disabledClass}`}>
        <span className="text-xs font-medium text-gray-600">Prompt template</span>
        <textarea
          className="border border-gray-200 rounded px-2 py-1.5 text-sm resize-y min-h-[80px] font-mono text-xs"
          value={promptTemplate}
          onChange={(e) => setPromptTemplate(e.target.value)}
          onBlur={() => {
            const val = promptTemplate || null;
            if (val !== edge.prompt_template) onSave({ prompt_template: val });
          }}
          disabled={readOnly}
        />
      </label>

      {toAgentPrompts.length > 0 && (
        <label className={`flex flex-col gap-1 ${disabledClass}`}>
          <span className="text-xs font-medium text-gray-600">Prompt (from target agent)</span>
          <select
            className="border border-gray-200 rounded px-2 py-1.5 text-sm"
            value={edge.prompt_id ?? ""}
            onChange={(e) => {
              const val = e.target.value || null;
              onSave({ prompt_id: val });
            }}
            disabled={readOnly}
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

      <label className={`flex items-center gap-2 ${disabledClass}`}>
        <input
          type="checkbox"
          checked={requiresApproval}
          onChange={(e) => {
            setRequiresApproval(e.target.checked);
            onSave({ requires_approval: e.target.checked });
          }}
          disabled={readOnly}
        />
        <span className="text-sm text-gray-700">Requires approval</span>
      </label>


      <label className={`flex flex-col gap-1 ${disabledClass}`}>
        <span className="text-xs font-medium text-gray-600">Max rounds</span>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={1}
            max={50}
            className="border border-gray-200 rounded px-2 py-1.5 text-sm w-20"
            value={maxRounds}
            onChange={(e) => setMaxRounds(Number(e.target.value))}
            onBlur={() => {
              const val = Math.max(1, Math.min(50, maxRounds));
              setMaxRounds(val);
              if (val !== edge.max_rounds) onSave({ max_rounds: val });
            }}
            disabled={readOnly}
          />
          <span className="text-xs text-gray-400">How many times this edge can be traversed</span>
        </div>
      </label>

      {!readOnly && (
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
      )}
    </div>
  );
}
