import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { createAgent, updateAgent, deleteAgent } from "../api/agents";
import { createTeam } from "../api/teams";
import {
  createWorkflow,
  createWorkflowEdge,
  updateWorkflowEdge,
  deleteWorkflowEdge,
} from "../api/workflows";
import type {
  AgentCreate,
  AgentUpdate,
  TeamCreate,
  WorkflowCreate,
  WorkflowEdgeCreate,
  WorkflowEdgeUpdate,
} from "../types";

/**
 * Provides imperative mutation functions for canvas editing.
 * Each function calls the API directly, invalidates relevant caches,
 * and logs errors to the console.
 */
export function useCanvasMutations() {
  const queryClient = useQueryClient();

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
      console.error("Failed to create team:", err);
    }
  }, [invalidateTeams]);

  const handleCreateAgent = useCallback(async (teamId: string, data: AgentCreate) => {
    try {
      await createAgent(teamId, data);
      invalidateAgents();
      invalidateTeams();
    } catch (err) {
      console.error("Failed to create agent:", err);
    }
  }, [invalidateAgents, invalidateTeams]);

  const handleUpdateAgent = useCallback(async (id: string, data: AgentUpdate) => {
    try {
      await updateAgent(id, data);
      invalidateAgents();
    } catch (err) {
      console.error("Failed to update agent:", err);
    }
  }, [invalidateAgents]);

  const handleDeleteAgent = useCallback(async (id: string) => {
    try {
      await deleteAgent(id);
      invalidateAgents();
      invalidateTeams();
      invalidateEdges();
    } catch (err) {
      console.error("Failed to delete agent:", err);
    }
  }, [invalidateAgents, invalidateTeams, invalidateEdges]);

  const handleCreateWorkflow = useCallback(async (teamId: string, data: WorkflowCreate) => {
    try {
      await createWorkflow(teamId, data);
      invalidateWorkflows();
    } catch (err) {
      console.error("Failed to create workflow:", err);
    }
  }, [invalidateWorkflows]);

  const handleCreateEdge = useCallback(async (workflowId: string, data: WorkflowEdgeCreate) => {
    try {
      await createWorkflowEdge(workflowId, data);
      invalidateEdges();
    } catch (err) {
      console.error("Failed to create edge:", err);
    }
  }, [invalidateEdges]);

  const handleUpdateEdge = useCallback(async (id: string, data: WorkflowEdgeUpdate) => {
    try {
      await updateWorkflowEdge(id, data);
      invalidateEdges();
    } catch (err) {
      console.error("Failed to update edge:", err);
    }
  }, [invalidateEdges]);

  const handleDeleteEdge = useCallback(async (id: string) => {
    try {
      await deleteWorkflowEdge(id);
      invalidateEdges();
    } catch (err) {
      console.error("Failed to delete edge:", err);
    }
  }, [invalidateEdges]);

  const handleSavePosition = useCallback(async (agentId: string, x: number, y: number) => {
    try {
      await updateAgent(agentId, { position_x: Math.round(x), position_y: Math.round(y) });
    } catch (err) {
      console.error("Failed to save position:", err);
      invalidateAgents();
    }
  }, [invalidateAgents]);

  return {
    handleCreateTeam,
    handleCreateAgent,
    handleUpdateAgent,
    handleDeleteAgent,
    handleCreateWorkflow,
    handleCreateEdge,
    handleUpdateEdge,
    handleDeleteEdge,
    handleSavePosition,
  };
}
