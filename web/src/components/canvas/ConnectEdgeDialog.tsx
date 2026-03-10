import { useState } from "react";
import type { Workflow } from "../../types";

interface ConnectEdgeDialogProps {
  workflows: Workflow[];
  fromAgentName: string;
  toAgentName: string;
  onSubmit: (workflowId: string, condition: string | null) => void;
  onCancel: () => void;
}

export function ConnectEdgeDialog({
  workflows,
  fromAgentName,
  toAgentName,
  onSubmit,
  onCancel,
}: ConnectEdgeDialogProps) {
  const [workflowId, setWorkflowId] = useState("");
  const [condition, setCondition] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!workflowId) return;
    onSubmit(workflowId, condition.trim() || null);
  };

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <form
        onSubmit={handleSubmit}
        className="bg-white rounded-lg shadow-lg p-5 w-[380px] flex flex-col gap-3"
      >
        <h3 className="text-sm font-semibold text-gray-900">Create edge</h3>
        <p className="text-xs text-gray-500">
          {fromAgentName} &rarr; {toAgentName}
        </p>

        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">Workflow *</span>
          <select
            className="border border-gray-300 rounded px-2 py-1.5 text-sm"
            value={workflowId}
            onChange={(e) => setWorkflowId(e.target.value)}
          >
            <option value="" disabled>Select workflow</option>
            {workflows.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">Condition (optional)</span>
          <input
            type="text"
            className="border border-gray-300 rounded px-2 py-1.5 text-sm"
            value={condition}
            onChange={(e) => setCondition(e.target.value)}
          />
        </label>

        <div className="flex gap-2 pt-2">
          <button
            type="submit"
            disabled={!workflowId}
            className="text-sm bg-blue-600 text-white rounded px-4 py-1.5 hover:bg-blue-700 disabled:opacity-50"
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
        </div>
      </form>
    </div>
  );
}
