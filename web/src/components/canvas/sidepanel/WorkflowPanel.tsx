import { useState, useCallback } from "react";
import type { Agent, Workflow, WorkflowEdge, WorkflowEdgeUpdate, WorkflowUpdate } from "../../../types";
import { PromptEditor, type PromptVariable } from "../../PromptEditor";

interface WorkflowPanelProps {
  teamId: string;
  workflows: Workflow[];
  workflowEdges: WorkflowEdge[];
  agents: Agent[];
  onUpdateEdge: (edgeId: string, workflowId: string, data: WorkflowEdgeUpdate) => void;
  onUpdateWorkflow: (workflowId: string, data: WorkflowUpdate) => void;
}

interface ChainStep {
  agent: Agent;
  forwardEdge: WorkflowEdge | null;
}

interface ReturnEdge {
  edge: WorkflowEdge;
  fromAgent: Agent;
  toAgent: Agent;
}

const EDGE_VARIABLES: PromptVariable[] = [
  { label: "Комментарий агента", value: "{{comment}}" },
];

function buildChain(
  workflow: Workflow,
  edges: WorkflowEdge[],
  agents: Agent[],
): { steps: ChainStep[]; returnEdges: ReturnEdge[] } {
  const agentMap = new Map(agents.map((a) => [a.id, a]));
  const forwardEdges: WorkflowEdge[] = [];
  const returnEdgesList: ReturnEdge[] = [];
  const visited = new Set<string>();
  const steps: ChainStep[] = [];

  const startAgent = agentMap.get(workflow.starting_agent_id);
  if (!startAgent) return { steps: [], returnEdges: [] };

  let currentId = workflow.starting_agent_id;
  visited.add(currentId);
  steps.push({ agent: startAgent, forwardEdge: null });

  let safety = 20;
  while (safety-- > 0) {
    const outgoing = edges.filter((e) => e.from_agent_id === currentId);
    let advanced = false;
    for (const edge of outgoing) {
      if (!visited.has(edge.to_agent_id)) {
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
  onUpdateEdge,
  onUpdateWorkflow,
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
        <WorkflowPromptEditor
          workflow={selectedWorkflow}
          edges={wfEdges}
          agents={agents}
          onUpdateEdge={onUpdateEdge}
          onUpdateWorkflow={onUpdateWorkflow}
        />
      )}
    </div>
  );
}

// ── Workflow prompt editor with chain ────────────────────────────────────────

function WorkflowPromptEditor({
  workflow,
  edges,
  agents,
  onUpdateEdge,
  onUpdateWorkflow,
}: {
  workflow: Workflow;
  edges: WorkflowEdge[];
  agents: Agent[];
  onUpdateEdge: (edgeId: string, workflowId: string, data: WorkflowEdgeUpdate) => void;
  onUpdateWorkflow: (workflowId: string, data: WorkflowUpdate) => void;
}) {
  const { steps, returnEdges } = buildChain(workflow, edges, agents);
  const [startingPrompt, setStartingPrompt] = useState(workflow.starting_prompt);

  const handleStartingPromptBlur = useCallback(() => {
    if (startingPrompt !== workflow.starting_prompt) {
      onUpdateWorkflow(workflow.id, { starting_prompt: startingPrompt });
    }
  }, [startingPrompt, workflow, onUpdateWorkflow]);

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
    <div className="space-y-4">
      {/* Starting prompt */}
      <div>
        <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide mb-2">
          Стартовый промпт
        </p>
        <PromptEditor
          value={startingPrompt}
          onChange={setStartingPrompt}
          onBlur={handleStartingPromptBlur}
          variables={[]}
          placeholder="Промпт для первого агента..."
          rows={3}
        />
      </div>

      {/* Chain with edge prompts */}
      <div>
        <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide mb-3">
          Цепочка
        </p>
        <div className="space-y-0">
          {steps.map((step, idx) => {
            const isFirst = idx === 0;
            const isLast = idx === steps.length - 1;
            const agentReturns = returnsByFrom.get(step.agent.id) || [];

            return (
              <div key={step.agent.id}>
                {/* Forward edge with prompt */}
                {step.forwardEdge && (
                  <EdgePromptSection
                    edge={step.forwardEdge}
                    fromAgent={steps[idx - 1]?.agent}
                    toAgent={step.agent}
                    workflowId={workflow.id}
                    onUpdateEdge={onUpdateEdge}
                  />
                )}

                {/* Agent node */}
                <div className="flex items-start gap-3">
                  <div className="flex flex-col items-center">
                    <div className={`w-3 h-3 rounded-full border-2 ${
                      isFirst ? "bg-green-500 border-green-600" :
                      isLast && agentReturns.length === 0 ? "bg-red-400 border-red-500" :
                      "bg-blue-500 border-blue-600"
                    }`} />
                    {(!isLast || agentReturns.length > 0) && <div className="w-px h-4 bg-gray-300 mt-1" />}
                  </div>
                  <div className="flex-1 -mt-0.5">
                    <span className="text-sm font-medium text-gray-800">{step.agent.name}</span>
                    {isFirst && (
                      <span className="ml-2 text-[10px] text-green-600 bg-green-50 px-1.5 py-0.5 rounded">
                        старт
                      </span>
                    )}

                    {/* Return edges */}
                    {agentReturns.length > 0 && (
                      <div className="mt-2 space-y-2">
                        {agentReturns.map((re) => (
                          <ReturnEdgeSection
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
      </div>
    </div>
  );
}

// ── Forward edge prompt section ──────────────────────────────────────────────

function EdgePromptSection({
  edge,
  fromAgent,
  toAgent,
  workflowId,
  onUpdateEdge,
}: {
  edge: WorkflowEdge;
  fromAgent?: Agent;
  toAgent: Agent;
  workflowId: string;
  onUpdateEdge: (edgeId: string, workflowId: string, data: WorkflowEdgeUpdate) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [prompt, setPrompt] = useState(edge.prompt_template ?? "");

  const handleBlur = () => {
    const val = prompt || null;
    if (val !== edge.prompt_template) {
      onUpdateEdge(edge.id, workflowId, { prompt_template: val });
    }
  };

  const label = fromAgent ? `${fromAgent.name} → ${toAgent.name}` : `→ ${toAgent.name}`;

  return (
    <div className="flex items-start gap-3 py-1">
      <div className="flex flex-col items-center">
        <div className="w-px h-full bg-gray-300" style={{ minHeight: expanded ? 80 : 24 }} />
      </div>
      <div className="flex-1 -mt-0.5">
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 text-[11px] text-gray-500 hover:text-gray-700 w-full text-left"
        >
          {edge.requires_approval ? (
            <span title="Требует одобрения">🔒</span>
          ) : (
            <span title="Автоматически">⚡</span>
          )}
          <span className="font-medium">{edge.condition || label}</span>
          <span className="text-gray-300 ml-auto">{expanded ? "▲" : "▼"}</span>
        </button>
        {expanded && (
          <div className="mt-2 mb-1">
            <PromptEditor
              value={prompt}
              onChange={setPrompt}
              onBlur={handleBlur}
              variables={EDGE_VARIABLES}
              placeholder={`Промпт перехода ${label}...`}
              rows={2}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Return edge section ──────────────────────────────────────────────────────

function ReturnEdgeSection({
  returnEdge,
  workflowId,
  onUpdateEdge,
}: {
  returnEdge: ReturnEdge;
  workflowId: string;
  onUpdateEdge: (edgeId: string, workflowId: string, data: WorkflowEdgeUpdate) => void;
}) {
  const { edge, toAgent } = returnEdge;
  const [expanded, setExpanded] = useState(false);
  const [prompt, setPrompt] = useState(edge.prompt_template ?? "");
  const [rounds, setRounds] = useState(edge.max_rounds);

  const handlePromptBlur = () => {
    const val = prompt || null;
    if (val !== edge.prompt_template) {
      onUpdateEdge(edge.id, workflowId, { prompt_template: val });
    }
  };

  const handleRoundsSave = () => {
    const val = Math.max(1, Math.min(50, rounds));
    setRounds(val);
    if (val !== edge.max_rounds) {
      onUpdateEdge(edge.id, workflowId, { max_rounds: val });
    }
  };

  return (
    <div className="bg-amber-50 border border-amber-200 rounded px-2.5 py-2 space-y-2">
      <div className="flex items-center gap-1.5">
        <span className="text-amber-500 text-xs">↻</span>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex-1 flex items-center gap-1.5 text-left"
        >
          <span className="text-xs text-amber-700 font-medium">
            → {toAgent.name}
          </span>
          {edge.requires_approval && <span className="text-[10px]">🔒</span>}
          <span className="text-amber-300 ml-auto text-[10px]">{expanded ? "▲" : "▼"}</span>
        </button>
        <span className="text-gray-300 text-xs">|</span>
        <input
          type="number"
          min={1}
          max={50}
          value={rounds}
          onChange={(e) => setRounds(Number(e.target.value))}
          onBlur={handleRoundsSave}
          onKeyDown={(e) => e.key === "Enter" && handleRoundsSave()}
          className="w-10 border border-amber-300 rounded px-1 py-0.5 text-xs text-center bg-white"
        />
        <span className="text-[10px] text-gray-400">раз</span>
      </div>
      {expanded && (
        <PromptEditor
          value={prompt}
          onChange={setPrompt}
          onBlur={handlePromptBlur}
          variables={EDGE_VARIABLES}
          placeholder={`Промпт возврата → ${toAgent.name}...`}
          rows={2}
        />
      )}
    </div>
  );
}
