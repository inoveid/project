import { useState, useEffect } from "react";
import type { Agent, Workflow, WorkflowEdge, AgentUpdate, WorkflowEdgeUpdate, WorkflowUpdate } from "../../../types";
import { AgentGeneralTab } from "./AgentGeneralTab";
import { AgentHandoffTab } from "./AgentHandoffTab";
import { AgentSubAgentsTab } from "./AgentSubAgentsTab";
import { EdgePanel } from "./EdgePanel";
import { WorkflowPanel } from "./WorkflowPanel";

export type SidePanelSelection =
  | { type: "agent"; agentId: string }
  | { type: "agent-create"; teamId: string }
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
  onCreateEdge: (workflowId: string, fromAgentId: string, toAgentId: string) => void;
  onUpdateWorkflow: (workflowId: string, data: WorkflowUpdate) => void;
  onCreateWorkflow: (teamId: string, data: { name: string; starting_agent_id: string; starting_prompt: string }) => void;
  onDeleteWorkflow: (id: string) => void;
  onCreateAgent: (teamId: string, data: { name: string; system_prompt: string; role: string }) => void;
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
}: SidePanelProps) {
  const [activeTab, setActiveTab] = useState<AgentTab>("general");

  useEffect(() => {
    if (selection.type === "edge") {
      setActiveTab("general");
    }
  }, [selection]);

  if (selection.type === "agent") {
    const agent = agents.find((a) => a.id === selection.agentId);
    if (!agent) return null;

    const outgoingEdges = workflowEdges.filter((e) => e.from_agent_id === agent.id);

    return (
      <PanelShell title={agent.name} onClose={onClose}>
        <TabBar
          tabs={AGENT_TABS}
          active={activeTab}
          onChange={setActiveTab}
        />
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

  if (selection.type === "agent-create") {
    return (
      <PanelShell title="Новый агент" onClose={onClose}>
        <div className="flex-1 overflow-y-auto p-4">
          <AgentCreateForm
            onSubmit={(data) => {
              onCreateAgent(selection.teamId, data);
              onClose();
            }}
          />
        </div>
      </PanelShell>
    );
  }

  if (selection.type === "team") {
    return (
      <PanelShell title="Workflow" onClose={onClose}>
        <div className="flex-1 overflow-y-auto">
          <WorkflowPanel
            teamId={selection.teamId}
            workflows={workflows}
            workflowEdges={workflowEdges}
            agents={agents}
            onUpdateEdge={onUpdateEdge}
            onUpdateWorkflow={onUpdateWorkflow}
            onCreateWorkflow={onCreateWorkflow}
            onDeleteWorkflow={onDeleteWorkflow}
          />
        </div>
      </PanelShell>
    );
  }

  // Edge selection
  const rawEdgeId = selection.edgeId.replace(/^edge-/, "");
  const edge = workflowEdges.find((e) => e.id === rawEdgeId);
  if (!edge) return null;

  const toAgent = agents.find((a) => a.id === edge.to_agent_id);

  const isEdgeLocked = lockedWorkflowIds.has(edge.workflow_id);

  return (
    <PanelShell title="Edge settings" onClose={onClose}>
      <div className="flex-1 overflow-y-auto p-4">
        <EdgePanel
          key={edge.id}
          edge={edge}
          onSave={(data) => onUpdateEdge(edge.id, edge.workflow_id, data)}
          onDelete={() => onDeleteEdge(edge.id)}
          readOnly={isEdgeLocked}
        />
      </div>
    </PanelShell>
  );
}

const AGENT_TABS: Array<{ id: AgentTab; label: string }> = [
  { id: "general", label: "General" },
  { id: "handoff", label: "Handoff" },
  { id: "sub-agents", label: "Sub-agents" },
];

function PanelShell({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      className="w-[400px] bg-white border-l border-gray-200 flex flex-col h-full animate-slide-in"
      data-testid="side-panel"
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <h2 className="text-sm font-semibold text-gray-900 truncate">{title}</h2>
        <button
          type="button"
          className="text-gray-400 hover:text-gray-600 text-lg leading-none"
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
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-gray-600">Имя <span className="text-red-400">*</span></span>
        <input
          type="text"
          className="border border-gray-200 rounded px-2 py-1.5 text-sm"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Например: Developer"
          autoFocus
          maxLength={100}
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-gray-600">Системный промпт <span className="text-red-400">*</span></span>
        <textarea
          className="border border-gray-200 rounded px-2 py-1.5 text-sm resize-y min-h-[120px] font-mono text-xs"
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
          placeholder="Инструкции для агента..."
        />
      </label>

      <button
        type="submit"
        disabled={!canSubmit}
        className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50 self-start"
      >
        Создать
      </button>
    </form>
  );
}