import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  compareEvalRuns,
  createEvalCase,
  createEvalRun,
  deleteEvalCase,
  getEvalCases,
  getEvalRun,
  getEvalRunResults,
  getEvalRuns,
} from "../api/evaluations";
import type { EvalCaseCreate, EvalRunCreate } from "../types";

const CASES_KEY = ["eval-cases"] as const;
const RUNS_KEY = ["eval-runs"] as const;

export function useEvalCases(agentRole?: string, tag?: string) {
  return useQuery({
    queryKey: [...CASES_KEY, agentRole, tag],
    queryFn: () => getEvalCases(agentRole, tag),
  });
}

export function useCreateEvalCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: EvalCaseCreate) => createEvalCase(data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: CASES_KEY });
    },
  });
}

export function useDeleteEvalCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteEvalCase(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: CASES_KEY });
    },
  });
}

export function useEvalRuns(promptVersion?: string) {
  return useQuery({
    queryKey: [...RUNS_KEY, promptVersion],
    queryFn: () => getEvalRuns(promptVersion),
    refetchInterval: 5000,
  });
}

export function useEvalRun(id: string) {
  return useQuery({
    queryKey: [...RUNS_KEY, id],
    queryFn: () => getEvalRun(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" || status === "pending" ? 3000 : false;
    },
  });
}

export function useEvalRunResults(runId: string) {
  return useQuery({
    queryKey: [...RUNS_KEY, runId, "results"],
    queryFn: () => getEvalRunResults(runId),
    enabled: !!runId,
  });
}

export function useCreateEvalRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: EvalRunCreate) => createEvalRun(data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: RUNS_KEY });
    },
  });
}

export function useCompareRuns(runA: string, runB: string) {
  return useQuery({
    queryKey: ["eval-compare", runA, runB],
    queryFn: () => compareEvalRuns(runA, runB),
    enabled: !!runA && !!runB,
  });
}
