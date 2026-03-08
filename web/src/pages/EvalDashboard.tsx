import { useState } from "react";
import { useEvalCases, useEvalRuns } from "../hooks/useEvaluations";
import { EvalRunsList } from "../components/eval/EvalRunsList";
import { EvalCasesList } from "../components/eval/EvalCasesList";
import { EvalRunDetail } from "../components/eval/EvalRunDetail";
import { NewEvalRunForm } from "../components/eval/NewEvalRunForm";

type Tab = "runs" | "cases";

export function EvalDashboard() {
  const [tab, setTab] = useState<Tab>("runs");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [showNewRun, setShowNewRun] = useState(false);
  const { data: runs, isLoading: runsLoading } = useEvalRuns();
  const { data: cases, isLoading: casesLoading } = useEvalCases();

  if (selectedRunId) {
    return (
      <EvalRunDetail
        runId={selectedRunId}
        onBack={() => setSelectedRunId(null)}
      />
    );
  }

  const completedRuns = runs?.filter((r) => r.status === "completed") ?? [];
  const latestPassRate = completedRuns.length > 0 ? completedRuns[0].pass_rate : null;
  const totalCases = cases?.length ?? 0;

  return (
    <div>
      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-3 mb-8">
        <div className="bg-white rounded-lg border p-4">
          <p className="text-sm text-gray-500">Eval Runs</p>
          <p className="text-2xl font-bold text-gray-900">{runs?.length ?? 0}</p>
        </div>
        <div className="bg-white rounded-lg border p-4">
          <p className="text-sm text-gray-500">Golden Cases</p>
          <p className="text-2xl font-bold text-gray-900">{totalCases}</p>
        </div>
        <div className="bg-white rounded-lg border p-4">
          <p className="text-sm text-gray-500">Latest Pass Rate</p>
          <p className="text-2xl font-bold text-gray-900">
            {latestPassRate != null ? `${(latestPassRate * 100).toFixed(0)}%` : "—"}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-4 mb-6">
        <div className="flex border rounded-lg overflow-hidden">
          <button
            onClick={() => setTab("runs")}
            className={`px-4 py-2 text-sm font-medium ${
              tab === "runs"
                ? "bg-blue-600 text-white"
                : "bg-white text-gray-700 hover:bg-gray-50"
            }`}
          >
            Runs
          </button>
          <button
            onClick={() => setTab("cases")}
            className={`px-4 py-2 text-sm font-medium ${
              tab === "cases"
                ? "bg-blue-600 text-white"
                : "bg-white text-gray-700 hover:bg-gray-50"
            }`}
          >
            Cases ({totalCases})
          </button>
        </div>

        {tab === "runs" && (
          <button
            onClick={() => setShowNewRun(!showNewRun)}
            className="ml-auto bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
          >
            {showNewRun ? "Cancel" : "New Eval Run"}
          </button>
        )}
      </div>

      {/* New run form */}
      {showNewRun && tab === "runs" && (
        <div className="mb-6">
          <NewEvalRunForm
            cases={cases ?? []}
            onCreated={() => setShowNewRun(false)}
          />
        </div>
      )}

      {/* Content */}
      {tab === "runs" && (
        <EvalRunsList
          runs={runs ?? []}
          isLoading={runsLoading}
          onSelectRun={setSelectedRunId}
        />
      )}
      {tab === "cases" && (
        <EvalCasesList cases={cases ?? []} isLoading={casesLoading} />
      )}
    </div>
  );
}
