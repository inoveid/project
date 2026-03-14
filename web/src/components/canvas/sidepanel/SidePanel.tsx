import { useState, useEffect } from "react";
import type { Agent, Team, Workflow, WorkflowEdge, AgentUpdate, TeamUpdate, WorkflowEdgeUpdate, WorkflowUpdate } from "../../../types";
import { AgentGeneralTab } from "./AgentGeneralTab";
import { AgentHandoffTab } from "./AgentHandoffTab";
import { AgentSubAgentsTab } from "./AgentSubAgentsTab";
import { WorkflowPanel } from "./WorkflowPanel";
import { TeamPanel } from "./TeamPanel";

export type SidePanelSelection =
  | { type: "agent"; agentId: string }
  | { type: "agents"; teamId: string; selectedAgentId?: string }
  | { type: "workflows"; teamId: string; selectedWorkflowId?: string }
  | { type: "edge"; edgeId: string }
  | { type: "team"; teamId: string };

interface SidePanelProps {
  selection: SidePanelSelection;
  agents: Agent[];
  workflows: Workflow[];
  workflowEdges: WorkflowEdge[];
  lockedWorkflowIds: Set<string>;
  onClose: () => void;
  onUpdateAgent: (id: string, teamId: string, data: AgentUpdate) => void;
  onDeleteAgent: (id: string, teamId: string) => void;
  onUpdateEdge: (edgeId: string, workflowId: string, data: WorkflowEdgeUpdate) => void;
  onDeleteEdge: (edgeId: string) => void;
  onCreateEdge: (workflowId: string, fromAgentId: string, toAgentId: string, condition?: string, promptTemplate?: string) => void;
  onUpdateWorkflow: (workflowId: string, data: WorkflowUpdate) => void;
  onCreateWorkflow: (teamId: string, data: { name: string; starting_agent_id: string; starting_prompt: string }) => void;
  onDeleteWorkflow: (id: string) => void;
  onCreateAgent: (teamId: string, data: { name: string; system_prompt: string; role: string }) => void;
  teams: Team[];
  onUpdateTeam: (id: string, data: TeamUpdate) => void;
  onDeleteTeam: (id: string) => void;
  onSelectAgent?: (agentId: string, teamId: string) => void;
}

type AgentTab = "general" | "handoff" | "sub-agents";

export function SidePanel({
  selection,
  agents,
  workflows,
  workflowEdges,
  lockedWorkflowIds,
  onClose,
  onUpdateAgent,
  onDeleteAgent,
  onUpdateEdge,
  onDeleteEdge,
  onCreateEdge,
  onUpdateWorkflow,
  onCreateWorkflow,
  onDeleteWorkflow,
  onCreateAgent,
  teams,
  onUpdateTeam,
  onDeleteTeam,
  onSelectAgent,
}: SidePanelProps) {
  const [activeTab, setActiveTab] = useState<AgentTab>("general");

  useEffect(() => {
    if (selection.type === "edge") {
      setActiveTab("general");
    }
  }, [selection]);

  // ── Agents panel (list + CRUD) ──
  if (selection.type === "agents") {
    return (
      <AgentsPanel
        teamId={selection.teamId}
        initialAgentId={selection.selectedAgentId}
        agents={agents}
        workflows={workflows}
        workflowEdges={workflowEdges}
        onClose={onClose}
        onUpdateAgent={onUpdateAgent}
        onDeleteAgent={onDeleteAgent}
        onCreateAgent={onCreateAgent}
        onUpdateEdge={onUpdateEdge}
        onCreateEdge={onCreateEdge}
      />
    );
  }

  // ── Workflows panel ──
  if (selection.type === "workflows") {
    return (
      <WorkflowsPanelWrapper
        key={`${selection.teamId}-${selection.selectedWorkflowId ?? "default"}`}
        teamId={selection.teamId}
        initialWorkflowId={selection.selectedWorkflowId}
        workflows={workflows}
        workflowEdges={workflowEdges}
        agents={agents}
        onClose={onClose}
        onUpdateEdge={onUpdateEdge}
        onUpdateWorkflow={onUpdateWorkflow}
        onCreateWorkflow={onCreateWorkflow}
        onDeleteWorkflow={onDeleteWorkflow}
        onCreateEdge={onCreateEdge}
        onDeleteEdge={onDeleteEdge}
        onSelectAgent={onSelectAgent}
      />
    );
  }

  // ── Team settings panel ──
  if (selection.type === "team") {
    return (
      <TeamPanelWrapper
        teamId={selection.teamId}
        teams={teams}
        onClose={onClose}
        onUpdateTeam={onUpdateTeam}
        onDeleteTeam={onDeleteTeam}
      />
    );
  }

  // ── Single agent (legacy, kept for compatibility) ──
  if (selection.type === "agent") {
    const agent = agents.find((a) => a.id === selection.agentId);
    if (!agent) return null;

    const outgoingEdges = workflowEdges.filter((e) => e.from_agent_id === agent.id);

    return (
      <PanelShell title={agent.name} onClose={onClose}>
        <TabBar tabs={AGENT_TABS} active={activeTab} onChange={setActiveTab} />
        <div className="flex-1 overflow-y-auto p-4">
          {activeTab === "general" && (
            <AgentGeneralTab
              key={agent.id}
              agent={agent}
              onSave={(data) => onUpdateAgent(agent.id, agent.team_id, data)}
              onDelete={() => onDeleteAgent(agent.id, agent.team_id)}
            />
          )}
          {activeTab === "handoff" && (
            <AgentHandoffTab
              key={agent.id}
              agent={agent}
              outgoingEdges={outgoingEdges}
              workflows={workflows}
              allAgents={agents}
              onUpdateEdge={onUpdateEdge}
              onCreateEdge={(workflowId, toAgentId) =>
                onCreateEdge(workflowId, agent.id, toAgentId)
              }
            />
          )}
          {activeTab === "sub-agents" && (
            <AgentSubAgentsTab
              key={agent.id}
              agent={agent}
              onSave={(data) => onUpdateAgent(agent.id, agent.team_id, data)}
            />
          )}
        </div>
      </PanelShell>
    );
  }

  // ── Edge selection (redirected to workflow panel) ──
  return null;
}

// ── Agents panel with selector ──────────────────────────────────────────────

function AgentsPanel({
  teamId,
  initialAgentId,
  agents,
  workflows,
  workflowEdges,
  onClose,
  onUpdateAgent,
  onDeleteAgent,
  onCreateAgent,
  onUpdateEdge,
  onCreateEdge,
}: {
  teamId: string;
  initialAgentId?: string;
  agents: Agent[];
  workflows: Workflow[];
  workflowEdges: WorkflowEdge[];
  onClose: () => void;
  onUpdateAgent: (id: string, teamId: string, data: AgentUpdate) => void;
  onDeleteAgent: (id: string, teamId: string) => void;
  onCreateAgent: (teamId: string, data: { name: string; system_prompt: string; role: string }) => void;
  teams: Team[];
  onUpdateTeam: (id: string, data: TeamUpdate) => void;
  onDeleteTeam: (id: string) => void;
  onSelectAgent?: (agentId: string, teamId: string) => void;
  onUpdateEdge: (edgeId: string, workflowId: string, data: WorkflowEdgeUpdate) => void;
  onCreateEdge: (workflowId: string, fromAgentId: string, toAgentId: string, condition?: string, promptTemplate?: string) => void;
}) {
  const teamAgents = agents.filter((a) => a.team_id === teamId);
  const [selectedAgentId, setSelectedAgentId] = useState<string>(
    initialAgentId ?? teamAgents[0]?.id ?? "",
  );
  const [showCreateForm, setShowCreateForm] = useState(teamAgents.length === 0);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [activeTab, setActiveTab] = useState<AgentTab>("general");
  const [knownAgentIds, setKnownAgentIds] = useState(() => new Set(teamAgents.map(a => a.id)));

  useEffect(() => {
    if (initialAgentId && initialAgentId !== selectedAgentId) {
      setSelectedAgentId(initialAgentId);
      setShowCreateForm(false);
      setShowDeleteConfirm(false);
    }
  }, [initialAgentId]);

  // Detect new/deleted agents
  useEffect(() => {
    const currentIds = new Set(teamAgents.map(a => a.id));
    // Find newly added agent
    const newAgent = teamAgents.find(a => !knownAgentIds.has(a.id));
    if (newAgent) {
      setSelectedAgentId(newAgent.id);
      setShowCreateForm(false);
      setShowDeleteConfirm(false);
    }
    // If selected agent was deleted, select first remaining
    if (!currentIds.has(selectedAgentId) && teamAgents.length > 0) {
      setSelectedAgentId(teamAgents[0].id);
    }
    if (teamAgents.length === 0) {
      setShowCreateForm(true);
    }
    setKnownAgentIds(currentIds);
  }, [teamAgents]);

  const selectedAgent = teamAgents.find((a) => a.id === selectedAgentId);
  const outgoingEdges = selectedAgent
    ? workflowEdges.filter((e) => e.from_agent_id === selectedAgent.id)
    : [];

  return (
    <PanelShell
      title="Agents"
      onClose={onClose}
      headerButtons={
        teamAgents.length > 0 ? (
          <>
            <button
              type="button"
              onClick={() => { setShowCreateForm(!showCreateForm); setShowDeleteConfirm(false); }}
              className="text-[11px] text-blue-600 border border-blue-200 rounded px-2 py-0.5 hover:bg-blue-50"
            >
              {showCreateForm ? "Отмена" : "Добавить"}
            </button>
            {selectedAgent && !showCreateForm && (
              <button
                type="button"
                onClick={() => { setShowDeleteConfirm(!showDeleteConfirm); }}
                className="text-[11px] text-red-500 border border-red-200 rounded px-2 py-0.5 hover:bg-red-50"
              >
                Удалить
              </button>
            )}
          </>
        ) : undefined
      }
    >
      <div className="flex-1 overflow-y-auto">
        <div className="p-4 space-y-4">
          {/* Create form */}
          {showCreateForm && (
            <AgentCreateForm
              onSubmit={(data) => {
                onCreateAgent(teamId, data);
                setShowCreateForm(false);
              }}
            />
          )}

          {/* Delete confirm */}
          {showDeleteConfirm && selectedAgent && (
            <div className="p-3 border border-red-200 rounded bg-red-50 space-y-2">
              <p className="text-sm text-red-700">
                Удалить <b>{selectedAgent.name}</b>?
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="text-sm bg-red-600 text-white rounded px-3 py-1 hover:bg-red-700"
                  onClick={() => {
                    onDeleteAgent(selectedAgent.id, teamId);
                    setShowDeleteConfirm(false);
                    setSelectedAgentId(teamAgents.find(a => a.id !== selectedAgent.id)?.id ?? "");
                  }}
                >
                  Да, удалить
                </button>
                <button
                  type="button"
                  className="text-sm text-gray-500 hover:text-gray-700"
                  onClick={() => setShowDeleteConfirm(false)}
                >
                  Отмена
                </button>
              </div>
            </div>
          )}

          {/* Agent selector */}
          {!showCreateForm && teamAgents.length > 0 && (
            <>
              <select
                value={selectedAgentId}
                onChange={(e) => { setSelectedAgentId(e.target.value); setShowDeleteConfirm(false); }}
                className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
              >
                {teamAgents.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>

              {/* Agent tabs + content */}
              {selectedAgent && (
                <>
                  <TabBar tabs={AGENT_TABS} active={activeTab} onChange={setActiveTab} />
                  <div className="pt-2">
                    {activeTab === "general" && (
                      <AgentGeneralTab
                        key={selectedAgent.id}
                        agent={selectedAgent}
                        onSave={(data) => onUpdateAgent(selectedAgent.id, teamId, data)}
                        onDelete={() => {
                          onDeleteAgent(selectedAgent.id, teamId);
                          setSelectedAgentId(teamAgents.find(a => a.id !== selectedAgent.id)?.id ?? "");
                        }}
                      />
                    )}
                    {activeTab === "handoff" && (
                      <AgentHandoffTab
                        key={selectedAgent.id}
                        agent={selectedAgent}
                        outgoingEdges={outgoingEdges}
                        workflows={workflows}
                        allAgents={agents}
                        onUpdateEdge={onUpdateEdge}
                        onCreateEdge={(workflowId, toAgentId) =>
                          onCreateEdge(workflowId, selectedAgent.id, toAgentId)
                        }
                      />
                    )}
                    {activeTab === "sub-agents" && (
                      <AgentSubAgentsTab
                        key={selectedAgent.id}
                        agent={selectedAgent}
                        onSave={(data) => onUpdateAgent(selectedAgent.id, teamId, data)}
                      />
                    )}
                  </div>
                </>
              )}
            </>
          )}

          {!showCreateForm && teamAgents.length === 0 && (
            <p className="text-sm text-gray-400">Нет агентов в этой команде</p>
          )}
        </div>
      </div>
    </PanelShell>
  );
}

// ── Agent create form ───────────────────────────────────────────────────────

function AgentCreateForm({
  onSubmit,
}: {
  onSubmit: (data: { name: string; system_prompt: string; role: string }) => void;
}) {
  const [name, setName] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");

  const canSubmit = name.trim().length > 0 && systemPrompt.trim().length > 0;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    onSubmit({ name: name.trim(), system_prompt: systemPrompt.trim(), role: "agent" });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 p-3 border border-blue-200 rounded bg-blue-50/50">
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Имя <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          className="w-full border border-gray-300 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Например: Developer"
          autoFocus
          maxLength={100}
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Системный промпт <span className="text-red-400">*</span>
        </label>
        <textarea
          className="w-full border border-gray-300 rounded px-2.5 py-1.5 text-sm font-mono text-xs resize-y min-h-[120px] focus:outline-none focus:ring-2 focus:ring-blue-400"
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
          placeholder="Инструкции для агента..."
        />
      </div>
      <button
        type="submit"
        disabled={!canSubmit}
        className="text-sm bg-blue-600 text-white rounded px-3 py-1.5 hover:bg-blue-700 disabled:opacity-50"
      >
        Создать
      </button>
    </form>
  );
}

// ── Workflows panel wrapper ──────────────────────────────────────────────────

function WorkflowsPanelWrapper({
  teamId, initialWorkflowId, workflows, workflowEdges, agents, onClose,
  onUpdateEdge, onUpdateWorkflow, onCreateWorkflow, onDeleteWorkflow, onCreateEdge, onDeleteEdge,
  onSelectAgent,
}: {
  teamId: string;
  initialWorkflowId?: string;
  workflows: Workflow[];
  workflowEdges: WorkflowEdge[];
  agents: Agent[];
  onClose: () => void;
  onSelectAgent?: (agentId: string, teamId: string) => void;
  onUpdateEdge: (edgeId: string, workflowId: string, data: WorkflowEdgeUpdate) => void;
  onUpdateWorkflow: (workflowId: string, data: WorkflowUpdate) => void;
  onCreateWorkflow: (teamId: string, data: { name: string; starting_agent_id: string; starting_prompt: string }) => void;
  onDeleteWorkflow: (id: string) => void;
  onCreateEdge: (workflowId: string, fromAgentId: string, toAgentId: string, condition?: string, promptTemplate?: string) => void;
  onDeleteEdge: (edgeId: string) => void;
}) {
  const [headerButtons, setHeaderButtons] = useState<React.ReactNode>(null);
  return (
    <PanelShell title="Workflows" onClose={onClose} headerButtons={headerButtons}>
      <div className="flex-1 overflow-y-auto">
        <WorkflowPanel
          teamId={teamId}
          initialWorkflowId={initialWorkflowId}
          workflows={workflows}
          workflowEdges={workflowEdges}
          agents={agents}
          onUpdateEdge={onUpdateEdge}
          onUpdateWorkflow={onUpdateWorkflow}
          onCreateWorkflow={onCreateWorkflow}
          onDeleteWorkflow={onDeleteWorkflow}
          onCreateEdge={onCreateEdge}
          onDeleteEdge={onDeleteEdge}
          renderHeaderButtons={setHeaderButtons}
          onSelectAgent={(agentId) => {
            const agent = agents.find(a => a.id === agentId);
            if (agent) onSelectAgent?.(agentId, agent.team_id);
          }}
        />
      </div>
    </PanelShell>
  );
}

// ── Team panel wrapper ───────────────────────────────────────────────────────

function TeamPanelWrapper({
  teamId, teams, onClose, onUpdateTeam, onDeleteTeam,
}: {
  teamId: string;
  teams: Team[];
  onClose: () => void;
  onUpdateTeam: (id: string, data: TeamUpdate) => void;
  onDeleteTeam: (id: string) => void;
}) {
  const team = teams.find((t) => t.id === teamId);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  if (!team) return null;

  return (
    <PanelShell
      title={team.name}
      onClose={onClose}
      headerButtons={
        <button
          type="button"
          onClick={() => setShowDeleteConfirm(!showDeleteConfirm)}
          className="text-[11px] text-red-500 border border-red-200 rounded px-2 py-0.5 hover:bg-red-50"
        >
          Удалить
        </button>
      }
    >
      <div className="flex-1 overflow-y-auto p-4">
        {showDeleteConfirm && (
          <div className="p-3 border border-red-200 rounded bg-red-50 space-y-2 mb-4">
            <p className="text-sm text-red-700">Удалить команду <b>{team.name}</b>? Все агенты и связи будут удалены.</p>
            <div className="flex gap-2">
              <button type="button" className="text-sm bg-red-600 text-white rounded px-3 py-1 hover:bg-red-700"
                onClick={() => { onDeleteTeam(team.id); onClose(); }}>
                Да, удалить
              </button>
              <button type="button" className="text-sm text-gray-500 hover:text-gray-700"
                onClick={() => setShowDeleteConfirm(false)}>
                Отмена
              </button>
            </div>
          </div>
        )}
        <TeamPanel
          key={team.id}
          team={team}
          onSave={(data) => onUpdateTeam(team.id, data)}
          onDelete={() => { onDeleteTeam(team.id); onClose(); }}
        />
      </div>
    </PanelShell>
  );
}

// ── Shared components ───────────────────────────────────────────────────────

const AGENT_TABS: Array<{ id: AgentTab; label: string }> = [
  { id: "general", label: "General" },
  { id: "handoff", label: "Handoff" },
  { id: "sub-agents", label: "Sub-agents" },
];

function PanelShell({
  title,
  onClose,
  children,
  headerButtons,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  headerButtons?: React.ReactNode;
}) {
  return (
    <div
      className="absolute right-0 top-0 w-[400px] bg-white border-l border-gray-200 flex flex-col h-full animate-slide-in z-10 shadow-lg"
      data-testid="side-panel"
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-200">
        <h2 className="text-sm font-semibold text-gray-900 truncate">{title}</h2>
        {headerButtons && (
          <div className="flex items-center gap-1 ml-auto">
            {headerButtons}
          </div>
        )}
        <button
          type="button"
          className={`text-gray-400 hover:text-gray-600 text-lg leading-none ${headerButtons ? "" : "ml-auto"}`}
          onClick={onClose}
          aria-label="Close panel"
        >
          &times;
        </button>
      </div>
      {children}
    </div>
  );
}

function TabBar<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: Array<{ id: T; label: string }>;
  active: T;
  onChange: (id: T) => void;
}) {
  return (
    <div className="flex border-b border-gray-200">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={`flex-1 text-xs font-medium py-2 border-b-2 transition-colors ${
            active === tab.id
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
