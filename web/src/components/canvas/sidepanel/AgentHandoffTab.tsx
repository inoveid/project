import { useState } from "react";
import type { Agent, WorkflowEdge, Workflow, WorkflowEdgeUpdate } from "../../../types";

interface AgentHandoffTabProps {
  agent: Agent;
  outgoingEdges: WorkflowEdge[];
  workflows: Workflow[];
  allAgents: Agent[];
  onUpdateEdge: (edgeId: string, workflowId: string, data: WorkflowEdgeUpdate) => void;
  onCreateEdge: (workflowId: string, toAgentId: string) => void;
}

export function AgentHandoffTab({
  agent,
  outgoingEdges,
  workflows,
  allAgents,
  onUpdateEdge,
  onCreateEdge,
}: AgentHandoffTabProps) {
  const agentMap = new Map(allAgents.map((a) => [a.id, a]));
  const workflowMap = new Map(workflows.map((w) => [w.id, w]));

  const edgesByWorkflow = new Map<string, WorkflowEdge[]>();
  for (const edge of outgoingEdges) {
    const list = edgesByWorkflow.get(edge.workflow_id) ?? [];
    list.push(edge);
    edgesByWorkflow.set(edge.workflow_id, list);
  }

  const teamWorkflows = workflows.filter((w) => w.team_id === agent.team_id);

  return (
    <div className="flex flex-col gap-4">
      {Array.from(edgesByWorkflow.entries()).map(([wfId, edges]) => {
        const wf = workflowMap.get(wfId);
        return (
          <div key={wfId} className="border border-gray-200 rounded p-3">
            <h4 className="text-xs font-semibold text-gray-600 mb-2">
              {wf?.name ?? "Unknown workflow"}
            </h4>
            {edges.map((edge) => {
              const toAgent = agentMap.get(edge.to_agent_id);
              return (
                <div key={edge.id} className="flex flex-col gap-1 mb-2 pl-2 border-l-2 border-gray-100">
                  <span className="text-sm text-gray-800">
                    &rarr; {toAgent?.name ?? "Unknown agent"}
                  </span>
                  {edge.condition && (
                    <span className="text-xs text-gray-500">Condition: {edge.condition}</span>
                  )}
                  <label className="flex items-center gap-1.5 text-xs text-gray-600">
                    <input
                      type="checkbox"
                      checked={edge.requires_approval}
                      onChange={(e) =>
                        onUpdateEdge(edge.id, edge.workflow_id, {
                          requires_approval: e.target.checked,
                        })
                      }
                    />
                    Requires approval
                  </label>
                </div>
              );
            })}
          </div>
        );
      })}

      {teamWorkflows.length > 0 && (
        <div className="pt-2">
          <AddHandoffRule
            workflows={teamWorkflows}
            agents={allAgents.filter((a) => a.id !== agent.id)}
            onAdd={onCreateEdge}
          />
        </div>
      )}

      {outgoingEdges.length === 0 && teamWorkflows.length === 0 && (
        <p className="text-xs text-gray-400">No workflows in this team yet</p>
      )}
    </div>
  );
}

function AddHandoffRule({
  workflows,
  agents,
  onAdd,
}: {
  workflows: Workflow[];
  agents: Agent[];
  onAdd: (workflowId: string, toAgentId: string) => void;
}) {
  const [selectedWorkflowId, setSelectedWorkflowId] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState("");

  const handleAdd = () => {
    if (!selectedWorkflowId || !selectedAgentId) return;
    onAdd(selectedWorkflowId, selectedAgentId);
    setSelectedWorkflowId("");
    setSelectedAgentId("");
  };

  return (
    <details className="group">
      <summary className="text-sm text-blue-600 hover:text-blue-700 cursor-pointer">
        + Rule
      </summary>
      <div className="mt-2 flex flex-col gap-2 pl-2">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-gray-600">Workflow</span>
          <select
            className="border border-gray-200 rounded px-2 py-1 text-sm"
            value={selectedWorkflowId}
            onChange={(e) => setSelectedWorkflowId(e.target.value)}
          >
            <option value="" disabled>Select workflow</option>
            {workflows.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-gray-600">Target agent</span>
          <select
            className="border border-gray-200 rounded px-2 py-1 text-sm"
            value={selectedAgentId}
            onChange={(e) => setSelectedAgentId(e.target.value)}
          >
            <option value="" disabled>Select agent</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="text-xs bg-blue-600 text-white rounded px-3 py-1 hover:bg-blue-700 self-start"
          onClick={handleAdd}
        >
          Add
        </button>
      </div>
    </details>
  );
}
