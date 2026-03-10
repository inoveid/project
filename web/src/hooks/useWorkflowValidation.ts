import { useMemo } from "react";
import type { Agent, Workflow, WorkflowEdge, ValidationIssue } from "../types";

/**
 * Validate a single workflow and return a list of issues.
 */
export function validateWorkflow(
  workflow: Workflow,
  edges: WorkflowEdge[],
  agents: Agent[],
): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const workflowEdges = edges.filter((e) => e.workflow_id === workflow.id);
  const teamAgents = agents.filter((a) => a.team_id === workflow.team_id);

  // 1. Missing starting_prompt
  if (!workflow.starting_prompt || workflow.starting_prompt.trim() === "") {
    issues.push({
      type: "error",
      message: "Workflow has no starting prompt",
      workflowId: workflow.id,
    });
  }

  // 2. Check agents in this team for reachability / connectivity
  const agentsWithIncoming = new Set(workflowEdges.map((e) => e.to_agent_id));
  const agentsWithOutgoing = new Set(workflowEdges.map((e) => e.from_agent_id));

  for (const agent of teamAgents) {
    const isStarting = workflow.starting_agent_id === agent.id;
    const hasIncoming = agentsWithIncoming.has(agent.id);
    const hasOutgoing = agentsWithOutgoing.has(agent.id);
    const participatesInWorkflow =
      isStarting || hasIncoming || hasOutgoing;

    if (!participatesInWorkflow) continue;

    // Unreachable: participates but has no incoming and is not starting
    if (!isStarting && !hasIncoming && hasOutgoing) {
      issues.push({
        type: "warning",
        message: `Agent '${agent.name}' is unreachable (no incoming edges)`,
        nodeId: agent.id,
        workflowId: workflow.id,
      });
    }

    // Isolated: has no edges at all but is starting agent
    if (isStarting && !hasOutgoing && workflowEdges.length === 0) {
      issues.push({
        type: "warning",
        message: `Agent '${agent.name}' is the only agent in workflow with no edges`,
        nodeId: agent.id,
        workflowId: workflow.id,
      });
    }
  }

  return issues;
}

/**
 * Validate all workflows and collect team-level info issues.
 */
export function validateAll(
  workflows: Workflow[],
  edges: WorkflowEdge[],
  agents: Agent[],
  teamIds: string[],
): ValidationIssue[] {
  const issues: ValidationIssue[] = [];

  // Per-workflow validation
  for (const workflow of workflows) {
    issues.push(...validateWorkflow(workflow, edges, agents));
  }

  // Team-level info
  for (const teamId of teamIds) {
    const teamAgents = agents.filter((a) => a.team_id === teamId);
    const teamWorkflows = workflows.filter((w) => w.team_id === teamId);

    if (teamAgents.length === 0) {
      issues.push({
        type: "info",
        message: "Team has no agents",
        nodeId: teamId,
      });
    }

    if (teamWorkflows.length === 0 && teamAgents.length > 0) {
      issues.push({
        type: "info",
        message: "Team has no workflows",
        nodeId: teamId,
      });
    }
  }

  return issues;
}

/**
 * Hook that returns validation issues for the canvas.
 *
 * Also provides lookup maps for quick access by node/workflow.
 */
export function useWorkflowValidation(
  workflows: Workflow[],
  edges: WorkflowEdge[],
  agents: Agent[],
  teamIds: string[],
) {
  return useMemo(() => {
    const issues = validateAll(workflows, edges, agents, teamIds);

    const issuesByNode = new Map<string, ValidationIssue[]>();
    const issuesByWorkflow = new Map<string, ValidationIssue[]>();

    for (const issue of issues) {
      if (issue.nodeId) {
        const existing = issuesByNode.get(issue.nodeId) ?? [];
        existing.push(issue);
        issuesByNode.set(issue.nodeId, existing);
      }
      if (issue.workflowId) {
        const existing = issuesByWorkflow.get(issue.workflowId) ?? [];
        existing.push(issue);
        issuesByWorkflow.set(issue.workflowId, existing);
      }
    }

    return { issues, issuesByNode, issuesByWorkflow };
  }, [workflows, edges, agents, teamIds]);
}
