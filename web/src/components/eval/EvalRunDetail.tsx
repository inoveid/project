import { useState } from "react";
import { useEvalRun, useEvalRunResults } from "../../hooks/useEvaluations";
import type { EvalResult } from "../../types";

interface EvalRunDetailProps {
  runId: string;
  onBack: () => void;
}

function verdictBadge(verdict: string) {
  const colors: Record<string, string> = {
    pass: "bg-green-100 text-green-700",
    fail: "bg-red-100 text-red-700",
    error: "bg-yellow-100 text-yellow-700",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[verdict] ?? "bg-gray-100"}`}>
      {verdict.toUpperCase()}
    </span>
  );
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 70 ? "bg-green-500" : pct >= 40 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-600">{pct}%</span>
    </div>
  );
}

function ResultExpanded({ result }: { result: EvalResult }) {
  return (
    <div className="bg-gray-50 border-t px-4 py-4 space-y-4">
      {/* Criteria scores */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 mb-2">Criteria Scores</h4>
        <div className="space-y-2">
          {Object.entries(result.criteria_scores).map(([name, data]) => (
            <div key={name} className="flex items-center gap-3">
              <span className="text-sm text-gray-600 w-48 truncate">{name}</span>
              <ScoreBar score={data.score} />
              <span className="text-xs text-gray-500 truncate flex-1">{data.reasoning}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Judge reasoning */}
      {result.judge_reasoning && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-1">Judge Reasoning</h4>
          <p className="text-sm text-gray-600 whitespace-pre-wrap bg-white border rounded p-3">
            {result.judge_reasoning}
          </p>
        </div>
      )}

      {/* Token usage */}
      {Object.keys(result.token_usage).length > 0 && (
        <div className="flex gap-4 text-xs text-gray-500">
          {Object.entries(result.token_usage).map(([key, val]) => (
            <span key={key}>{key}: {val}</span>
          ))}
          {result.duration_ms != null && <span>duration: {result.duration_ms}ms</span>}
        </div>
      )}
    </div>
  );
}

export function EvalRunDetail({ runId, onBack }: EvalRunDetailProps) {
  const { data: run, isLoading: runLoading } = useEvalRun(runId);
  const { data: results, isLoading: resultsLoading } = useEvalRunResults(runId);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (runLoading || resultsLoading) {
    return <p className="text-gray-500">Loading...</p>;
  }

  if (!run) {
    return <p className="text-red-600">Run not found</p>;
  }

  const passRate = run.pass_rate != null ? Math.round(run.pass_rate * 100) : null;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={onBack}
          className="text-gray-500 hover:text-gray-700 text-sm"
        >
          &larr; Back
        </button>
        <h2 className="text-lg font-semibold text-gray-900">{run.name}</h2>
        <code className="text-xs bg-gray-100 px-2 py-0.5 rounded">{run.prompt_version}</code>
      </div>

      {/* Summary */}
      <div className="grid gap-4 sm:grid-cols-4 mb-6">
        <div className="bg-white rounded-lg border p-3">
          <p className="text-xs text-gray-500">Status</p>
          <p className="text-sm font-medium">{run.status}</p>
        </div>
        <div className="bg-white rounded-lg border p-3">
          <p className="text-xs text-gray-500">Pass Rate</p>
          <p className="text-lg font-bold">{passRate != null ? `${passRate}%` : "—"}</p>
        </div>
        <div className="bg-white rounded-lg border p-3">
          <p className="text-xs text-gray-500">Passed / Total</p>
          <p className="text-sm font-medium">
            <span className="text-green-600">{run.passed_cases}</span> / {run.total_cases}
          </p>
        </div>
        <div className="bg-white rounded-lg border p-3">
          <p className="text-xs text-gray-500">Model</p>
          <p className="text-xs font-medium truncate">{run.model}</p>
        </div>
      </div>

      {/* Results table */}
      {results && results.length > 0 ? (
        <div className="bg-white rounded-lg border overflow-hidden">
          {results.map((result) => (
            <div key={result.id}>
              <div
                onClick={() => setExpandedId(expandedId === result.id ? null : result.id)}
                className="flex items-center gap-4 px-4 py-3 hover:bg-gray-50 cursor-pointer border-b"
              >
                <span className="text-sm text-gray-400 w-8">
                  {expandedId === result.id ? "▾" : "▸"}
                </span>
                {verdictBadge(result.verdict)}
                <span className="text-sm text-gray-600 truncate flex-1">
                  {result.case_id.slice(0, 8)}...
                </span>
                <ScoreBar score={result.score} />
              </div>
              {expandedId === result.id && <ResultExpanded result={result} />}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-gray-500">
          {run.status === "running" ? "Evaluation in progress..." : "No results yet."}
        </p>
      )}
    </div>
  );
}
