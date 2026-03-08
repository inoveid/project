import type {
  EvalCase,
  EvalCaseCreate,
  EvalComparison,
  EvalResult,
  EvalRun,
  EvalRunCreate,
  EvalRunSummary,
} from "../types";
import { fetchApi } from "./client";

// ── EvalCase ────────────────────────────────────────────────────────────────

export function getEvalCases(agentRole?: string, tag?: string): Promise<EvalCase[]> {
  const params = new URLSearchParams();
  if (agentRole) params.set("agent_role", agentRole);
  if (tag) params.set("tag", tag);
  const qs = params.toString();
  return fetchApi<EvalCase[]>(`/eval/cases${qs ? `?${qs}` : ""}`);
}

export function getEvalCase(id: string): Promise<EvalCase> {
  return fetchApi<EvalCase>(`/eval/cases/${id}`);
}

export function createEvalCase(data: EvalCaseCreate): Promise<EvalCase> {
  return fetchApi<EvalCase>("/eval/cases", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function deleteEvalCase(id: string): Promise<void> {
  return fetchApi<void>(`/eval/cases/${id}`, { method: "DELETE" });
}

// ── EvalRun ─────────────────────────────────────────────────────────────────

export function getEvalRuns(promptVersion?: string): Promise<EvalRunSummary[]> {
  const qs = promptVersion ? `?prompt_version=${encodeURIComponent(promptVersion)}` : "";
  return fetchApi<EvalRunSummary[]>(`/eval/runs${qs}`);
}

export function getEvalRun(id: string): Promise<EvalRun> {
  return fetchApi<EvalRun>(`/eval/runs/${id}`);
}

export function createEvalRun(data: EvalRunCreate): Promise<EvalRunSummary> {
  return fetchApi<EvalRunSummary>("/eval/runs", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getEvalRunResults(runId: string): Promise<EvalResult[]> {
  return fetchApi<EvalResult[]>(`/eval/runs/${runId}/results`);
}

// ── Comparison ──────────────────────────────────────────────────────────────

export function compareEvalRuns(runA: string, runB: string): Promise<EvalComparison> {
  return fetchApi<EvalComparison>(`/eval/compare?run_a=${runA}&run_b=${runB}`);
}
