import { useState, useCallback, useEffect } from "react";
import type { Agent, Workflow, WorkflowEdge, WorkflowEdgeUpdate, WorkflowUpdate } from "../../../types";
import { PromptEditor, type PromptVariable } from "../../PromptEditor";

interface WorkflowPanelProps {
  teamId: string;
  workflows: Workflow[];
  workflowEdges: WorkflowEdge[];
  agents: Agent[];
  onUpdateEdge: (edgeId: string, workflowId: string, data: WorkflowEdgeUpdate) => void;
  onUpdateWorkflow: (workflowId: string, data: WorkflowUpdate) => void;
  onCreateWorkflow: (teamId: string, data: { name: string; starting_agent_id: string; starting_prompt: string }) => void;
  onDeleteWorkflow: (id: string) => void;
  onCreateEdge: (workflowId: string, fromAgentId: string, toAgentId: string, condition?: string) => void;
  onDeleteEdge: (edgeId: string) => void;
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
  teamId, workflows, workflowEdges, agents,
  onUpdateEdge, onUpdateWorkflow, onCreateWorkflow, onDeleteWorkflow, onCreateEdge, onDeleteEdge,
  renderHeaderButtons,
}: WorkflowPanelProps & { renderHeaderButtons?: (buttons: React.ReactNode) => void }) {
  const teamWorkflows = workflows.filter((w) => w.team_id === teamId);
  const teamAgents = agents.filter((a) => a.team_id === teamId);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>(teamWorkflows[0]?.id ?? "");
  const [showCreateForm, setShowCreateForm] = useState(teamWorkflows.length === 0);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const selectedWorkflow = teamWorkflows.find((w) => w.id === selectedWorkflowId);
  const wfEdges = workflowEdges.filter((e) => e.workflow_id === selectedWorkflowId);

  useEffect(() => {
    if (!renderHeaderButtons) return;
    if (teamWorkflows.length === 0) { renderHeaderButtons(null); return; }
    renderHeaderButtons(
      <>
        <button type="button" onClick={() => { setShowCreateForm(v => !v); setShowDeleteConfirm(false); }}
          className="text-[11px] text-blue-600 border border-blue-200 rounded px-2 py-0.5 hover:bg-blue-50">
          {showCreateForm ? "Отмена" : "Добавить"}
        </button>
        {selectedWorkflow && !showCreateForm && (
          <button type="button" onClick={() => setShowDeleteConfirm(v => !v)}
            className="text-[11px] text-red-500 border border-red-200 rounded px-2 py-0.5 hover:bg-red-50">
            Удалить
          </button>
        )}
      </>
    );
  }, [showCreateForm, showDeleteConfirm, selectedWorkflow, teamWorkflows.length, renderHeaderButtons]);

  return (
    <div className="p-4 space-y-4">

      {showDeleteConfirm && selectedWorkflow && (
        <div className="p-3 border border-red-200 rounded bg-red-50 space-y-2">
          <p className="text-sm text-red-700">Удалить <b>{selectedWorkflow.name}</b>? Все связи будут удалены.</p>
          <div className="flex gap-2">
            <button type="button" className="text-sm bg-red-600 text-white rounded px-3 py-1 hover:bg-red-700"
              onClick={() => { onDeleteWorkflow(selectedWorkflow.id); setShowDeleteConfirm(false); setSelectedWorkflowId(teamWorkflows.find(w => w.id !== selectedWorkflow.id)?.id ?? ""); }}>
              Да, удалить
            </button>
            <button type="button" className="text-sm text-gray-500 hover:text-gray-700" onClick={() => setShowDeleteConfirm(false)}>Отмена</button>
          </div>
        </div>
      )}

      {showCreateForm && (
        <CreateWorkflowInline teamId={teamId} agents={teamAgents}
          onSubmit={(data) => { onCreateWorkflow(teamId, data); setShowCreateForm(false); }}
          onCancel={() => setShowCreateForm(false)} />
      )}

      {!showCreateForm && teamWorkflows.length > 0 && (
        <>
          <select value={selectedWorkflowId} onChange={(e) => { setSelectedWorkflowId(e.target.value); setShowDeleteConfirm(false); }}
            className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm">
            {teamWorkflows.map((w) => (<option key={w.id} value={w.id}>{w.name}</option>))}
          </select>
          {selectedWorkflow && (
            <WorkflowPromptEditor key={selectedWorkflow.id} workflow={selectedWorkflow} edges={wfEdges} agents={agents}
              onUpdateEdge={onUpdateEdge} onUpdateWorkflow={onUpdateWorkflow} onCreateEdge={onCreateEdge} onDeleteEdge={onDeleteEdge} />
          )}
        </>
      )}

      {!showCreateForm && teamWorkflows.length === 0 && (
        <p className="text-sm text-gray-400">Нет workflow в этой команде</p>
      )}
    </div>
  );
}

function WorkflowPromptEditor({
  workflow, edges, agents, onUpdateEdge, onUpdateWorkflow, onCreateEdge, onDeleteEdge,
}: {
  workflow: Workflow; edges: WorkflowEdge[]; agents: Agent[];
  onUpdateEdge: (edgeId: string, workflowId: string, data: WorkflowEdgeUpdate) => void;
  onUpdateWorkflow: (workflowId: string, data: WorkflowUpdate) => void;
  onCreateEdge: (workflowId: string, fromAgentId: string, toAgentId: string, condition?: string) => void;
  onDeleteEdge: (edgeId: string) => void;
}) {
  const teamAgents = agents.filter(a => a.team_id === workflow.team_id);
  const { steps, returnEdges } = buildChain(workflow, edges, agents);
  const [startingPrompt, setStartingPrompt] = useState(workflow.starting_prompt);
  const [workflowName, setWorkflowName] = useState(workflow.name);
  const [showAddEdge, setShowAddEdge] = useState(false);
  const [newEdgeFrom, setNewEdgeFrom] = useState("");
  const [newEdgeTo, setNewEdgeTo] = useState("");
  const [newEdgeCondition, setNewEdgeCondition] = useState("");
  const [allExpanded, setAllExpanded] = useState(false);

  const handleStartingPromptBlur = useCallback(() => {
    if (startingPrompt !== workflow.starting_prompt) onUpdateWorkflow(workflow.id, { starting_prompt: startingPrompt });
  }, [startingPrompt, workflow, onUpdateWorkflow]);

  const handleNameBlur = useCallback(() => {
    const trimmed = workflowName.trim();
    if (trimmed && trimmed !== workflow.name) onUpdateWorkflow(workflow.id, { name: trimmed });
  }, [workflowName, workflow, onUpdateWorkflow]);

  const handleAddEdge = () => {
    if (newEdgeFrom && newEdgeTo && newEdgeFrom !== newEdgeTo) {
      onCreateEdge(workflow.id, newEdgeFrom, newEdgeTo, newEdgeCondition.trim() || undefined);
      setShowAddEdge(false); setNewEdgeFrom(""); setNewEdgeTo(""); setNewEdgeCondition("");
    }
  };

  if (steps.length === 0) return <p className="text-xs text-gray-400">Цепочка пуста</p>;

  const returnsByFrom = new Map<string, ReturnEdge[]>();
  for (const re of returnEdges) {
    const list = returnsByFrom.get(re.fromAgent.id) || [];
    list.push(re);
    returnsByFrom.set(re.fromAgent.id, list);
  }

  const hasEdges = edges.length > 0;

  return (
    <div className="space-y-4">
      <div>
        <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide mb-2">Название</p>
        <input type="text" value={workflowName} onChange={(e) => setWorkflowName(e.target.value)} onBlur={handleNameBlur}
          className="w-full border border-gray-300 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
      </div>

      <div>
        <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide mb-2">Стартовый промпт</p>
        <PromptEditor value={startingPrompt} onChange={setStartingPrompt} onBlur={handleStartingPromptBlur}
          variables={[]} placeholder="Промпт для первого агента..." rows={3} />
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Цепочка</p>
          {hasEdges && (
            <button type="button" onClick={() => setAllExpanded(!allExpanded)} className="text-[11px] text-blue-600 hover:text-blue-700">
              {allExpanded ? "Скрыть все" : "Показать все"}
            </button>
          )}
        </div>
        <div className="space-y-0">
          {steps.map((step, idx) => {
            const isFirst = idx === 0;
            const isLast = idx === steps.length - 1;
            const agentReturns = returnsByFrom.get(step.agent.id) || [];
            return (
              <div key={step.agent.id}>
                {step.forwardEdge && (
                  <EdgePromptSection edge={step.forwardEdge} fromAgent={steps[idx - 1]?.agent} toAgent={step.agent}
                    workflowId={workflow.id} onUpdateEdge={onUpdateEdge} onDeleteEdge={onDeleteEdge} forceExpanded={allExpanded} />
                )}
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
                    {isFirst && <span className="ml-2 text-[10px] text-green-600 bg-green-50 px-1.5 py-0.5 rounded">старт</span>}
                    {agentReturns.length > 0 && (
                      <div className="mt-2 space-y-2">
                        {agentReturns.map((re) => (
                          <ReturnEdgeSection key={re.edge.id} returnEdge={re} workflowId={workflow.id}
                            onUpdateEdge={onUpdateEdge} onDeleteEdge={onDeleteEdge} forceExpanded={allExpanded} />
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="pt-2">
          {!showAddEdge ? (
            <button type="button" onClick={() => setShowAddEdge(true)} className="text-xs text-blue-600 hover:text-blue-700">
              + Добавить переход
            </button>
          ) : (
            <div className="p-3 border border-blue-200 rounded bg-blue-50/50 space-y-2">
              <input type="text" value={newEdgeCondition} onChange={(e) => setNewEdgeCondition(e.target.value)}
                placeholder="Название перехода (опционально)"
                className="w-full border border-gray-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-blue-400" />
              <div className="flex gap-2">
                <select value={newEdgeFrom} onChange={(e) => setNewEdgeFrom(e.target.value)}
                  className="flex-1 border border-gray-300 rounded px-2 py-1 text-xs">
                  <option value="">От...</option>
                  {teamAgents.map(a => (<option key={a.id} value={a.id}>{a.name}</option>))}
                </select>
                <span className="text-xs text-gray-400 self-center">→</span>
                <select value={newEdgeTo} onChange={(e) => setNewEdgeTo(e.target.value)}
                  className="flex-1 border border-gray-300 rounded px-2 py-1 text-xs">
                  <option value="">К...</option>
                  {teamAgents.filter(a => a.id !== newEdgeFrom).map(a => (<option key={a.id} value={a.id}>{a.name}</option>))}
                </select>
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={handleAddEdge} disabled={!newEdgeFrom || !newEdgeTo || newEdgeFrom === newEdgeTo}
                  className="text-xs bg-blue-600 text-white rounded px-2.5 py-1 hover:bg-blue-700 disabled:opacity-50">Добавить</button>
                <button type="button" onClick={() => { setShowAddEdge(false); setNewEdgeFrom(""); setNewEdgeTo(""); setNewEdgeCondition(""); }}
                  className="text-xs text-gray-500 hover:text-gray-700">Отмена</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function EdgePromptSection({
  edge, fromAgent, toAgent, workflowId, onUpdateEdge, onDeleteEdge, forceExpanded,
}: {
  edge: WorkflowEdge; fromAgent?: Agent; toAgent: Agent; workflowId: string;
  onUpdateEdge: (edgeId: string, workflowId: string, data: WorkflowEdgeUpdate) => void;
  onDeleteEdge: (edgeId: string) => void;
  forceExpanded: boolean;
}) {
  const [localExpanded, setLocalExpanded] = useState(false);
  const expanded = forceExpanded || localExpanded;
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [prompt, setPrompt] = useState(edge.prompt_template ?? "");
  const [condition, setCondition] = useState(edge.condition ?? "");

  const handlePromptBlur = () => { const val = prompt || null; if (val !== edge.prompt_template) onUpdateEdge(edge.id, workflowId, { prompt_template: val }); };
  const handleConditionBlur = () => { const val = condition.trim() || null; if (val !== edge.condition) onUpdateEdge(edge.id, workflowId, { condition: val }); };
  const label = fromAgent ? `${fromAgent.name} → ${toAgent.name}` : `→ ${toAgent.name}`;

  return (
    <div className="flex items-start gap-3 py-1">
      <div className="flex flex-col items-center">
        <div className="w-px h-full bg-gray-300" style={{ minHeight: expanded ? 80 : 24 }} />
      </div>
      <div className="flex-1 -mt-0.5">
        <div className={`rounded border px-2.5 py-1.5 cursor-pointer transition-colors ${expanded ? "bg-blue-50 border-blue-200" : "bg-gray-50 border-gray-200 hover:bg-blue-50 hover:border-blue-200"}`}
          onClick={() => setLocalExpanded(!localExpanded)}>
          <div className="flex items-center gap-2 text-[11px]">
            {edge.requires_approval ? <span title="Требует одобрения">🔒</span> : <span title="Автоматически">⚡</span>}
            <span className="font-medium text-gray-700">{edge.condition || label}</span>
            <span className="text-gray-300 ml-auto">{expanded ? "▲" : "▼"}</span>
          </div>
        </div>
        {expanded && (
          <div className="mt-2 mb-1 space-y-3">
            <div>
              <p className="text-[10px] text-gray-400 mb-1">Название перехода</p>
              <input type="text" value={condition} onChange={(e) => setCondition(e.target.value)} onBlur={handleConditionBlur}
                placeholder={label} className="w-full border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-blue-400" />
            </div>
            <div>
              <p className="text-[10px] text-gray-400 mb-1">Промпт перехода</p>
              <PromptEditor value={prompt} onChange={setPrompt} onBlur={handlePromptBlur} variables={EDGE_VARIABLES}
                placeholder={`Промпт перехода ${label}...`} rows={2} />
            </div>
            {!showDeleteConfirm ? (
              <button type="button" onClick={(e) => { e.stopPropagation(); setShowDeleteConfirm(true); }}
                className="text-[11px] text-red-500 hover:text-red-700">Удалить переход</button>
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-red-600">Удалить?</span>
                <button type="button" onClick={(e) => { e.stopPropagation(); onDeleteEdge(edge.id); }}
                  className="text-[11px] bg-red-600 text-white rounded px-2 py-0.5 hover:bg-red-700">Да</button>
                <button type="button" onClick={(e) => { e.stopPropagation(); setShowDeleteConfirm(false); }}
                  className="text-[11px] text-gray-500 hover:text-gray-700">Нет</button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ReturnEdgeSection({
  returnEdge, workflowId, onUpdateEdge, onDeleteEdge, forceExpanded,
}: {
  returnEdge: ReturnEdge; workflowId: string;
  onUpdateEdge: (edgeId: string, workflowId: string, data: WorkflowEdgeUpdate) => void;
  onDeleteEdge: (edgeId: string) => void;
  forceExpanded: boolean;
}) {
  const { edge, toAgent } = returnEdge;
  const [localExpanded, setLocalExpanded] = useState(false);
  const expanded = forceExpanded || localExpanded;
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [prompt, setPrompt] = useState(edge.prompt_template ?? "");
  const [rounds, setRounds] = useState(edge.max_rounds);
  const [condition, setCondition] = useState(edge.condition ?? "");

  const handlePromptBlur = () => { const val = prompt || null; if (val !== edge.prompt_template) onUpdateEdge(edge.id, workflowId, { prompt_template: val }); };
  const handleRoundsSave = () => { const val = Math.max(1, Math.min(50, rounds)); setRounds(val); if (val !== edge.max_rounds) onUpdateEdge(edge.id, workflowId, { max_rounds: val }); };
  const handleConditionBlur = () => { const val = condition.trim() || null; if (val !== edge.condition) onUpdateEdge(edge.id, workflowId, { condition: val }); };

  return (
    <div className="bg-amber-50 border border-amber-200 rounded px-2.5 py-2 space-y-2">
      <div className="flex items-center gap-1.5">
        <span className="text-amber-500 text-xs">↻</span>
        <button type="button" onClick={() => setLocalExpanded(!localExpanded)} className="flex-1 flex items-center gap-1.5 text-left">
          <span className="text-xs text-amber-700 font-medium">{edge.condition || `→ ${toAgent.name}`}</span>
          {edge.requires_approval && <span className="text-[10px]">🔒</span>}
          <span className="text-amber-300 ml-auto text-[10px]">{expanded ? "▲" : "▼"}</span>
        </button>
        <span className="text-gray-300 text-xs">|</span>
        <input type="number" min={1} max={50} value={rounds} onChange={(e) => setRounds(Number(e.target.value))}
          onBlur={handleRoundsSave} onKeyDown={(e) => e.key === "Enter" && handleRoundsSave()}
          className="w-10 border border-amber-300 rounded px-1 py-0.5 text-xs text-center bg-white" />
        <span className="text-[10px] text-gray-400">раз</span>
      </div>
      {expanded && (
        <div className="space-y-3">
          <div>
            <p className="text-[10px] text-gray-400 mb-1">Название перехода</p>
            <input type="text" value={condition} onChange={(e) => setCondition(e.target.value)} onBlur={handleConditionBlur}
              placeholder={`→ ${toAgent.name}`} className="w-full border border-amber-200 rounded px-2 py-1 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-amber-400" />
          </div>
          <div>
            <p className="text-[10px] text-gray-400 mb-1">Промпт возврата</p>
            <PromptEditor value={prompt} onChange={setPrompt} onBlur={handlePromptBlur} variables={EDGE_VARIABLES}
              placeholder={`Промпт возврата → ${toAgent.name}...`} rows={2} />
          </div>
          {!showDeleteConfirm ? (
            <button type="button" onClick={() => setShowDeleteConfirm(true)} className="text-[11px] text-red-500 hover:text-red-700">Удалить переход</button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-red-600">Удалить?</span>
              <button type="button" onClick={() => onDeleteEdge(edge.id)} className="text-[11px] bg-red-600 text-white rounded px-2 py-0.5 hover:bg-red-700">Да</button>
              <button type="button" onClick={() => setShowDeleteConfirm(false)} className="text-[11px] text-gray-500 hover:text-gray-700">Нет</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CreateWorkflowInline({ teamId, agents, onSubmit, onCancel }: {
  teamId: string; agents: Agent[];
  onSubmit: (data: { name: string; starting_agent_id: string; starting_prompt: string }) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [startingAgentId, setStartingAgentId] = useState("");
  const [startingPrompt, setStartingPrompt] = useState("");
  const isValid = name.trim() && startingAgentId && startingPrompt.trim();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid) return;
    onSubmit({ name: name.trim(), starting_agent_id: startingAgentId, starting_prompt: startingPrompt.trim() });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 p-3 border border-blue-200 rounded bg-blue-50/50">
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Название</label>
        <input type="text" value={name} onChange={(e) => setName(e.target.value)}
          className="w-full border border-gray-300 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          placeholder="Например: Dev → Review" autoFocus />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Стартовый агент</label>
        <select value={startingAgentId} onChange={(e) => setStartingAgentId(e.target.value)}
          className="w-full border border-gray-300 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400">
          <option value="">— выбрать —</option>
          {agents.map((a) => (<option key={a.id} value={a.id}>{a.name}</option>))}
        </select>
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Стартовый промпт</label>
        <textarea value={startingPrompt} onChange={(e) => setStartingPrompt(e.target.value)}
          className="w-full border border-gray-300 rounded px-2.5 py-1.5 text-sm font-mono resize-y min-h-[60px] focus:outline-none focus:ring-2 focus:ring-blue-400"
          placeholder="Промпт для первого агента..." rows={3} />
      </div>
      <div className="flex gap-2">
        <button type="submit" disabled={!isValid} className="text-sm bg-blue-600 text-white rounded px-3 py-1.5 hover:bg-blue-700 disabled:opacity-50">Создать</button>
        <button type="button" onClick={onCancel} className="text-sm text-gray-500 hover:text-gray-700">Отмена</button>
      </div>
    </form>
  );
}
