import { useState } from "react";
import { useCreateEvalRun } from "../../hooks/useEvaluations";
import type { EvalCase } from "../../types";

interface NewEvalRunFormProps {
  cases: EvalCase[];
  onCreated: () => void;
}

export function NewEvalRunForm({ cases, onCreated }: NewEvalRunFormProps) {
  const createRun = useCreateEvalRun();
  const [name, setName] = useState("");
  const [promptVersion, setPromptVersion] = useState("");
  const [promptSnapshot, setPromptSnapshot] = useState("");
  const [selectedCaseIds, setSelectedCaseIds] = useState<Set<string>>(new Set());

  function toggleCase(id: string) {
    setSelectedCaseIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function selectAll() {
    setSelectedCaseIds(new Set(cases.map((c) => c.id)));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    createRun.mutate(
      {
        name,
        prompt_version: promptVersion,
        prompt_snapshot: promptSnapshot,
        case_ids: selectedCaseIds.size > 0 ? Array.from(selectedCaseIds) : undefined,
      },
      { onSuccess: onCreated },
    );
  }

  const isValid = name.trim() && promptVersion.trim() && promptSnapshot.trim();

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg border p-4 space-y-4">
      <h3 className="font-medium text-gray-900">New Eval Run</h3>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="block text-sm text-gray-600 mb-1">Run Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Developer prompt v2.1"
            className="w-full border rounded px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">Prompt Version</label>
          <input
            value={promptVersion}
            onChange={(e) => setPromptVersion(e.target.value)}
            placeholder="e.g. v2.1"
            className="w-full border rounded px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm text-gray-600 mb-1">Prompt Snapshot</label>
        <textarea
          value={promptSnapshot}
          onChange={(e) => setPromptSnapshot(e.target.value)}
          placeholder="Paste the full system prompt being evaluated..."
          rows={4}
          className="w-full border rounded px-3 py-2 text-sm font-mono"
        />
      </div>

      {/* Case selection */}
      {cases.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm text-gray-600">
              Select Cases ({selectedCaseIds.size} / {cases.length})
            </label>
            <button
              type="button"
              onClick={selectAll}
              className="text-xs text-blue-600 hover:underline"
            >
              Select All
            </button>
          </div>
          <div className="grid gap-1 sm:grid-cols-2 max-h-40 overflow-y-auto">
            {cases.map((c) => (
              <label
                key={c.id}
                className="flex items-center gap-2 text-sm text-gray-700 py-1 px-2 rounded hover:bg-gray-50 cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={selectedCaseIds.has(c.id)}
                  onChange={() => toggleCase(c.id)}
                  className="rounded"
                />
                {c.name}
              </label>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!isValid || createRun.isPending}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {createRun.isPending ? "Starting..." : "Start Eval Run"}
        </button>
      </div>

      {createRun.error && (
        <p className="text-sm text-red-600">{createRun.error.message}</p>
      )}
    </form>
  );
}
