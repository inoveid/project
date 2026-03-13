import { useState } from "react";
import type { Agent, Workflow, WorkflowEdge, WorkflowEdgeUpdate } from "../../../types";

interface WorkflowPanelProps {
  teamId: string;
  workflows: Workflow[];
  workflowEdges: WorkflowEdge[];
  agents: Agent[];
  lockedWorkflowIds: Set<string>;
  onUpdateEdge: (edgeId: string, workflowId: string, data: WorkflowEdgeUpdate) => void;
}

interface ChainStep {
  agent: Agent;
  forwardEdge: WorkflowEdge | null; // edge leading TO this agent (null for starting agent)
}

interface ReturnEdge {
  edge: WorkflowEdge;
  fromAgent: Agent;
  toAgent: Agent;
}

function buildChain(
  workflow: Workflow,
  edges: WorkflowEdge[],
  agents: Agent[],
): { steps: ChainStep[]; returnEdges: ReturnEdge[] } {
  const agentMap = new Map(agents.map((a) => [a.id, a]));
  const forwardEdges: WorkflowEdge[] = [];
  const returnEdgesList: ReturnEdge[] = [];

  // Start from starting_agent, follow forward edges
  const visited = new Set<string>();
  const steps: ChainStep[] = [];

  const startAgent = agentMap.get(workflow.starting_agent_id);
  if (!startAgent) return { steps: [], returnEdges: [] };

  // BFS/DFS to build linear chain
  let currentId = workflow.starting_agent_id;
  visited.add(currentId);
  steps.push({ agent: startAgent, forwardEdge: null });

  let safety = 20;
  while (safety-- > 0) {
    // Find outgoing edges from current agent
    const outgoing = edges.filter((e) => e.from_agent_id === currentId);
    let advanced = false;
    for (const edge of outgoing) {
      if (!visited.has(edge.to_agent_id)) {
        // Forward edge — new agent in chain
        const nextAgent = agentMap.get(edge.to_agent_id);
        if (nextAgent) {
          visited.add(edge.to_agent_id);
          steps.push({ agent: nextAgent, forwardEdge: edge });
          currentId = edge.to_agent_id;
          forwardEdges.push(edge);
          advanced = true;
          break;
        }
      }
    }
    if (!advanced) break;
  }

  // Identify return edges (to already-visited agents)
  for (const edge of edges) {
    if (!forwardEdges.includes(edge)) {
      const fromAgent = agentMap.get(edge.from_agent_id);
      const toAgent = agentMap.get(edge.to_agent_id);
      if (fromAgent && toAgent && visited.has(edge.from_agent_id) && visited.has(edge.to_agent_id)) {
        returnEdgesList.push({ edge, fromAgent, toAgent });
      }
    }
  }

  return { steps, returnEdges: returnEdgesList };
}

export function WorkflowPanel({
  teamId,
  workflows,
  workflowEdges,
  agents,
  lockedWorkflowIds,
  onUpdateEdge,
}: WorkflowPanelProps) {
  const teamWorkflows = workflows.filter((w) => w.team_id === teamId);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>(
    teamWorkflows[0]?.id ?? "",
  );

  const selectedWorkflow = teamWorkflows.find((w) => w.id === selectedWorkflowId);
  const wfEdges = workflowEdges.filter((e) => e.workflow_id === selectedWorkflowId);

  if (teamWorkflows.length === 0) {
    return (
      <div className="p-4 text-sm text-gray-400">
        Нет workflow в этой команде
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* Workflow selector */}
      {teamWorkflows.length > 1 ? (
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Workflow</label>
          <select
            value={selectedWorkflowId}
            onChange={(e) => setSelectedWorkflowId(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
          >
            {teamWorkflows.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </select>
        </div>
      ) : (
        <div className="text-sm font-medium text-gray-800">{teamWorkflows[0]!.name}</div>
      )}

      {selectedWorkflow && (
        <WorkflowChainStepper
          workflow={selectedWorkflow}
          edges={wfEdges}
          agents={agents}
          onUpdateEdge={onUpdateEdge}
        />
      )}
    </div>
  );
}

// ── Chain stepper ────────────────────────────────────────────────────────────

function WorkflowChainStepper({
  workflow,
  edges,
  agents,
  onUpdateEdge,
}: {
  workflow: Workflow;
  edges: WorkflowEdge[];
  agents: Agent[];
  onUpdateEdge: (edgeId: string, workflowId: string, data: WorkflowEdgeUpdate) => void;
}) {
  const { steps, returnEdges } = buildChain(workflow, edges, agents);

  if (steps.length === 0) {
    return <p className="text-xs text-gray-400">Цепочка пуста</p>;
  }

  // Group return edges by fromAgent
  const returnsByFrom = new Map<string, ReturnEdge[]>();
  for (const re of returnEdges) {
    const list = returnsByFrom.get(re.fromAgent.id) || [];
    list.push(re);
    returnsByFrom.set(re.fromAgent.id, list);
  }

  return (
    <div className="space-y-0">
      <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide mb-3">Цепочка</p>
      {steps.map((step, idx) => {
        const isFirst = idx === 0;
        const isLast = idx === steps.length - 1;
        const agentReturns = returnsByFrom.get(step.agent.id) || [];

        return (
          <div key={step.agent.id}>
            {/* Forward edge info */}
            {step.forwardEdge && (
              <EdgeConnector edge={step.forwardEdge} />
            )}

            {/* Agent node */}
            <div className="flex items-start gap-3">
              <div className="flex flex-col items-center">
                <div className={`w-3 h-3 rounded-full border-2 ${
                  isFirst ? "bg-green-500 border-green-600" :
                  isLast && agentReturns.length === 0 ? "bg-red-400 border-red-500" :
                  "bg-blue-500 border-blue-600"
                }`} />
                {!isLast && <div className="w-px h-4 bg-gray-300 mt-1" />}
              </div>
              <div className="flex-1 -mt-0.5">
                <span className="text-sm font-medium text-gray-800">{step.agent.name}</span>
                {isFirst && (
                  <span className="ml-2 text-[10px] text-green-600 bg-green-50 px-1.5 py-0.5 rounded">
                    старт
                  </span>
                )}

                {/* Return edges from this agent */}
                {agentReturns.length > 0 && (
                  <div className="mt-1.5 space-y-1">
                    {agentReturns.map((re) => (
                      <ReturnEdgeBadge
                        key={re.edge.id}
                        returnEdge={re}
                        workflowId={workflow.id}
                        onUpdateEdge={onUpdateEdge}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Forward edge connector (vertical line between agents) ────────────────────

function EdgeConnector({
  edge,
}: {
  edge: WorkflowEdge;
}) {
  return (
    <div className="flex items-center gap-3 py-0.5">
      <div className="flex flex-col items-center">
        <div className="w-px h-3 bg-gray-300" />
      </div>
      <div className="flex items-center gap-2 text-[11px] text-gray-400">
        {edge.requires_approval ? (
          <span title="Требует одобрения">🔒</span>
        ) : (
          <span title="Автоматически">⚡</span>
        )}
      </div>
    </div>
  );
}

// ── Return edge badge (cycle indicator with max_rounds) ──────────────────────

function ReturnEdgeBadge({
  returnEdge,
  workflowId,
  onUpdateEdge,
}: {
  returnEdge: ReturnEdge;
  workflowId: string;
  onUpdateEdge: (edgeId: string, workflowId: string, data: WorkflowEdgeUpdate) => void;
}) {
  const { edge, toAgent } = returnEdge;
  const [editing, setEditing] = useState(false);
  const [rounds, setRounds] = useState(edge.max_rounds);

  function handleSave() {
    if (rounds !== edge.max_rounds) {
      onUpdateEdge(edge.id, workflowId, { max_rounds: rounds });
    }
    setEditing(false);
  }

  return (
    <div className="flex items-center gap-1.5 bg-amber-50 border border-amber-200 rounded px-2 py-1">
      <span className="text-amber-500 text-xs">↻</span>
      <span className="text-xs text-amber-700">→ {toAgent.name}</span>
      <span className="text-gray-300 text-xs">|</span>
      {edge.requires_approval && <span className="text-[10px]" title="Требует одобрения">🔒</span>}
      {editing ? (
        <span className="flex items-center gap-1">
          <input
            type="number"
            min={1}
            max={99}
            value={rounds}
            onChange={(e) => setRounds(Number(e.target.value))}
            className="w-10 border border-amber-300 rounded px-1 py-0.5 text-xs text-center"
            autoFocus
            onKeyDown={(e) => e.key === "Enter" && handleSave()}
            onBlur={handleSave}
          />
          <span className="text-[10px] text-gray-400">раз</span>
        </span>
      ) : (
        <button
          type="button"
          className="text-xs text-amber-600 hover:text-amber-800 font-medium cursor-pointer"
          onClick={(e) => { e.stopPropagation(); setEditing(true); }}
          title={`Максимум ${edge.max_rounds} повторов`}
        >
          ×{edge.max_rounds}
        </button>
      )}
    </div>
  );
}
