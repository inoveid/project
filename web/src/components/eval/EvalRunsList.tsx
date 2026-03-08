import type { EvalRunSummary } from "../../types";

interface EvalRunsListProps {
  runs: EvalRunSummary[];
  isLoading: boolean;
  onSelectRun: (id: string) => void;
}

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-700",
    running: "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[status] ?? "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}

function passRateBar(rate: number | null) {
  if (rate == null) return <span className="text-gray-400 text-sm">—</span>;
  const pct = Math.round(rate * 100);
  const color = pct >= 80 ? "bg-green-500" : pct >= 50 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm font-medium text-gray-700">{pct}%</span>
    </div>
  );
}

export function EvalRunsList({ runs, isLoading, onSelectRun }: EvalRunsListProps) {
  if (isLoading) {
    return <p className="text-gray-500">Loading eval runs...</p>;
  }

  if (runs.length === 0) {
    return <p className="text-gray-500">No eval runs yet. Create one to get started.</p>;
  }

  return (
    <div className="bg-white rounded-lg border overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b">
          <tr>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Name</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Prompt Version</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Model</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Pass Rate</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Cases</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Date</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {runs.map((run) => (
            <tr
              key={run.id}
              onClick={() => onSelectRun(run.id)}
              className="hover:bg-gray-50 cursor-pointer"
            >
              <td className="px-4 py-3 font-medium text-gray-900">{run.name}</td>
              <td className="px-4 py-3 text-gray-600">
                <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">{run.prompt_version}</code>
              </td>
              <td className="px-4 py-3 text-gray-500 text-xs">{run.model}</td>
              <td className="px-4 py-3">{statusBadge(run.status)}</td>
              <td className="px-4 py-3">{passRateBar(run.pass_rate)}</td>
              <td className="px-4 py-3 text-gray-600">
                <span className="text-green-600">{run.passed_cases}</span>
                {" / "}
                <span>{run.total_cases}</span>
              </td>
              <td className="px-4 py-3 text-gray-500 text-xs">
                {new Date(run.created_at).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
