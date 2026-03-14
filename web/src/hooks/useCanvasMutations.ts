import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { createAgent, updateAgent, deleteAgent } from "../api/agents";
import { createTeam, updateTeam, deleteTeam } from "../api/teams";
import {
  createWorkflow,
  createWorkflowEdge,
  updateWorkflow,
  updateWorkflowEdge,
  deleteWorkflow,
  deleteWorkflowEdge,
} from "../api/workflows";
import type {
  AgentCreate,
  AgentUpdate,
  TeamCreate,
  TeamUpdate,
  WorkflowCreate,
  WorkflowEdgeCreate,
  WorkflowEdgeUpdate,
  WorkflowUpdate,
} from "../types";
import { useToast } from "./useToast";

function formatError(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

/**
 * Provides imperative mutation functions for canvas editing.
 * Each function calls the API directly, invalidates relevant caches,
 * and shows toast errors on failure.
 */
export function useCanvasMutations() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const invalidateTeams = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["teams"] });
  }, [queryClient]);

  const invalidateAgents = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["agents"] });
  }, [queryClient]);

  const invalidateWorkflows = useCallback(() => {
    void queryClient.invalidateQueries({
      predicate: (q) => q.queryKey[0] === "workflows",
    });
  }, [queryClient]);

  const invalidateEdges = useCallback(() => {
    void queryClient.invalidateQueries({
      predicate: (q) => q.queryKey[0] === "workflow-edges",
    });
  }, [queryClient]);

  const handleCreateTeam = useCallback(async (data: TeamCreate) => {
    try {
      await createTeam(data);
      invalidateTeams();
    } catch (err) {
      addToast({ type: "error", title: "Ошибка создания команды", message: formatError(err) });
    }
  }, [invalidateTeams, addToast]);

  const handleUpdateTeam = useCallback(async (id: string, data: TeamUpdate) => {
    try {
      await updateTeam(id, data);
      invalidateTeams();
    } catch (err) {
      addToast({ type: "error", title: "Ошибка обновления команды", message: formatError(err) });
    }
  }, [invalidateTeams, addToast]);

  const handleDeleteTeam = useCallback(async (id: string) => {
    try {
      await deleteTeam(id);
      invalidateTeams();
      invalidateAgents();
      invalidateWorkflows();
      invalidateEdges();
    } catch (err) {
      addToast({ type: "error", title: "Ошибка удаления команды", message: formatError(err) });
    }
  }, [invalidateTeams, invalidateAgents, invalidateWorkflows, invalidateEdges, addToast]);

  const handleCreateAgent = useCallback(async (teamId: string, data: AgentCreate) => {
    try {
      await createAgent(teamId, data);
      invalidateAgents();
      invalidateTeams();
    } catch (err) {
      addToast({ type: "error", title: "Ошибка создания агента", message: formatError(err) });
    }
  }, [invalidateAgents, invalidateTeams, addToast]);

  const handleUpdateAgent = useCallback(async (id: string, data: AgentUpdate) => {
    try {
      await updateAgent(id, data);
      invalidateAgents();
    } catch (err) {
      addToast({ type: "error", title: "Ошибка обновления агента", message: formatError(err) });
    }
  }, [invalidateAgents, addToast]);

  const handleDeleteAgent = useCallback(async (id: string) => {
    try {
      await deleteAgent(id);
      invalidateAgents();
      invalidateTeams();
      invalidateEdges();
    } catch (err) {
      const msg = formatError(err);
      if (msg.includes("409")) {
        addToast({ type: "warning", title: "Невозможно удалить агента", message: "Агент используется в активном workflow. Завершите задачу перед удалением." });
      } else {
        addToast({ type: "error", title: "Ошибка удаления агента", message: msg });
      }
    }
  }, [invalidateAgents, invalidateTeams, invalidateEdges, addToast]);

  const handleCreateWorkflow = useCallback(async (teamId: string, data: WorkflowCreate) => {
    try {
      await createWorkflow(teamId, data);
      invalidateWorkflows();
    } catch (err) {
      addToast({ type: "error", title: "Ошибка создания workflow", message: formatError(err) });
    }
  }, [invalidateWorkflows, addToast]);

  const handleUpdateWorkflow = useCallback(async (id: string, data: WorkflowUpdate) => {
    try {
      await updateWorkflow(id, data);
      invalidateWorkflows();
    } catch (err) {
      addToast({ type: "error", title: "Ошибка обновления workflow", message: formatError(err) });
    }
  }, [invalidateWorkflows, addToast]);

    const handleDeleteWorkflow = useCallback(async (id: string) => {
    try {
      await deleteWorkflow(id);
      invalidateWorkflows();
      invalidateEdges();
    } catch (err) {
      addToast({ type: "error", title: "Ошибка удаления workflow", message: formatError(err) });
    }
  }, [invalidateWorkflows, invalidateEdges, addToast]);

  const handleCreateEdge = useCallback(async (workflowId: string, data: WorkflowEdgeCreate) => {
    try {
      await createWorkflowEdge(workflowId, data);
      invalidateEdges();
    } catch (err) {
      addToast({ type: "error", title: "Ошибка создания связи", message: formatError(err) });
    }
  }, [invalidateEdges, addToast]);

  const handleUpdateEdge = useCallback(async (id: string, data: WorkflowEdgeUpdate) => {
    try {
      await updateWorkflowEdge(id, data);
      invalidateEdges();
    } catch (err) {
      addToast({ type: "error", title: "Ошибка обновления связи", message: formatError(err) });
    }
  }, [invalidateEdges, addToast]);

  const handleDeleteEdge = useCallback(async (id: string) => {
    try {
      await deleteWorkflowEdge(id);
      invalidateEdges();
    } catch (err) {
      addToast({ type: "error", title: "Ошибка удаления связи", message: formatError(err) });
    }
  }, [invalidateEdges, addToast]);

  const handleSavePosition = useCallback(async (agentId: string, x: number, y: number) => {
    try {
      await updateAgent(agentId, { position_x: Math.round(x), position_y: Math.round(y) });
    } catch (err) {
      addToast({ type: "error", title: "Ошибка сохранения позиции", message: formatError(err) });
      invalidateAgents();
    }
  }, [invalidateAgents, addToast]);

  return {
    handleCreateTeam,
    handleUpdateTeam,
    handleDeleteTeam,
    handleCreateAgent,
    handleUpdateAgent,
    handleDeleteAgent,
    handleCreateWorkflow,
    handleUpdateWorkflow,
    handleDeleteWorkflow,
    handleCreateEdge,
    handleUpdateEdge,
    handleDeleteEdge,
    handleSavePosition,
  };
}
