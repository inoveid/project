import type { EvalCase } from "../../types";

interface EvalCasesListProps {
  cases: EvalCase[];
  isLoading: boolean;
}

export function EvalCasesList({ cases, isLoading }: EvalCasesListProps) {
  if (isLoading) {
    return <p className="text-gray-500">Loading eval cases...</p>;
  }

  if (cases.length === 0) {
    return <p className="text-gray-500">No eval cases. Import golden dataset to start.</p>;
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {cases.map((c) => (
        <div key={c.id} className="bg-white rounded-lg border p-4">
          <div className="flex items-start justify-between mb-2">
            <h3 className="font-medium text-gray-900">{c.name}</h3>
            <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">
              {c.agent_role}
            </span>
          </div>
          <p className="text-sm text-gray-600 mb-3 line-clamp-2">{c.description}</p>
          <div className="flex flex-wrap gap-1 mb-3">
            {c.tags.map((tag) => (
              <span key={tag} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                {tag}
              </span>
            ))}
          </div>
          <div className="text-xs text-gray-500">
            {c.rubric.length} criteria | {c.expected_artifacts.length} expected artifacts
          </div>
        </div>
      ))}
    </div>
  );
}
