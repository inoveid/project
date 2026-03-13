import { useCallback, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  type NodeTypes,
  type EdgeTypes,
  type Connection,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useToast } from "../hooks/useToast";
import { useTeams } from "../hooks/useTeams";
import { useAllAgents } from "../hooks/useAgents";
import { useCanvasData } from "../hooks/useCanvasData";
import { useCanvasMutations } from "../hooks/useCanvasMutations";
import { useWorkflowValidation } from "../hooks/useWorkflowValidation";
import { useWorkflowLocks } from "../hooks/useWorkflowLock";
import { AgentNode } from "../components/canvas/AgentNode";
import { TeamGroupNode } from "../components/canvas/TeamGroupNode";
import { WorkflowEdgeComponent } from "../components/canvas/WorkflowEdge";
import { WorkflowFilter } from "../components/canvas/WorkflowFilter";
import { CreateTeamForm } from "../components/canvas/CreateTeamForm";
import { CreateAgentModal } from "../components/canvas/CreateAgentModal";
import { ConnectEdgeDialog } from "../components/canvas/ConnectEdgeDialog";
import { SidePanel, type SidePanelSelection } from "../components/canvas/sidepanel/SidePanel";
import {
  buildCanvasLayout,
  buildWorkflowColorMap,
  applyWorkflowFilter,
  stripNodePrefix,
} from "../components/canvas/canvasUtils";

const nodeTypes: NodeTypes = {
  agentNode: AgentNode,
  teamGroup: TeamGroupNode,
};

const edgeTypes: EdgeTypes = {
  workflowEdge: WorkflowEdgeComponent,
};

const DRAG_SAVE_DELAY = 500;

export function CanvasPage() {
  const { addToast } = useToast();
  const { data: teams, isLoading: teamsLoading } = useTeams();
  const { data: allAgents, isLoading: agentsLoading } = useAllAgents();
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [panelSelection, setPanelSelection] = useState<SidePanelSelection | null>(null);
  const [showCreateTeam, setShowCreateTeam] = useState(false);
  const [createAgentTeamId, setCreateAgentTeamId] = useState<string | null>(null);
  const [pendingConnection, setPendingConnection] = useState<{
    fromId: string;
    toId: string;
    fromName: string;
    toName: string;
  } | null>(null);

  const dragTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { allWorkflows, allEdges, isLoading: workflowsLoading } = useCanvasData(teams);
  const mutations = useCanvasMutations();

  // Validation & locks
  const teamIds = useMemo(() => (teams ?? []).map((t) => t.id), [teams]);
  const workflowIds = useMemo(
    () => allWorkflows.map((w) => w.id),
    [allWorkflows],
  );
  const { issuesByNode } = useWorkflowValidation(
    allWorkflows, allEdges, allAgents ?? [], teamIds,
  );
  const lockedWorkflowMap = useWorkflowLocks(workflowIds);
  const lockedWorkflowIds = useMemo(() => {
    const set = new Set<string>();
    for (const [id, locked] of lockedWorkflowMap) {
      if (locked) set.add(id);
    }
    return set;
  }, [lockedWorkflowMap]);

  // Callbacks for group node buttons
  const handleAddAgent = useCallback((teamId: string) => {
    setCreateAgentTeamId(teamId);
  }, []);

  const handleAddWorkflow = useCallback((teamId: string) => {
    setPanelSelection({ type: "team", teamId });
  }, []);

  // Build layout
  const { nodes, edges: rawEdges, workflowColorMap } = useMemo(() => {
    if (!teams) return { nodes: [], edges: [], workflowColorMap: new Map<string, string>() };
    const agentsByTeam = new Map<string, NonNullable<typeof allAgents>>();
    if (allAgents) {
      for (const agent of allAgents) {
        const existing = agentsByTeam.get(agent.team_id) ?? [];
        existing.push(agent);
        agentsByTeam.set(agent.team_id, existing);
      }
    }
    const colorMap = buildWorkflowColorMap(allWorkflows);
    const layout = buildCanvasLayout(
      teams, agentsByTeam, allWorkflows, allEdges, colorMap,
      new Set(),
      { onAddAgent: handleAddAgent, onAddWorkflow: handleAddWorkflow },
      { issuesByNode, lockedWorkflowIds },
    );
    return { ...layout, workflowColorMap: colorMap };
  }, [teams, allAgents, allWorkflows, allEdges, handleAddAgent, handleAddWorkflow, issuesByNode, lockedWorkflowIds]);

  const edges = useMemo(
    () => applyWorkflowFilter(rawEdges, selectedWorkflowId, allEdges, workflowColorMap),
    [rawEdges, selectedWorkflowId, allEdges, workflowColorMap],
  );

  // Node click → side panel
  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: { id: string; type?: string }) => {
      if (node.type === "agentNode") {
        setPanelSelection({ type: "agent", agentId: stripNodePrefix(node.id, "agent-") });
      } else if (node.type === "teamGroup") {
        const teamId = node.id.replace(/^team-/, "");
        setPanelSelection({ type: "team", teamId });
      }
    }, [],
  );

  // Edge click → side panel
  const handleEdgeClick = useCallback(
    (_event: React.MouseEvent, edge: { id: string }) => {
      setPanelSelection({ type: "edge", edgeId: edge.id });
    }, [],
  );

  // Drag & drop → debounced position save (allowed even when locked)
  const handleNodeDragStop = useCallback((_event: React.MouseEvent, node: Node) => {
    if (node.type !== "agentNode") return;
    const agentId = stripNodePrefix(node.id, "agent-");
    if (dragTimerRef.current) clearTimeout(dragTimerRef.current);
    dragTimerRef.current = setTimeout(() => {
      mutations.handleSavePosition(agentId, node.position.x, node.position.y);
      dragTimerRef.current = null;
    }, DRAG_SAVE_DELAY);
  }, [mutations]);

  // Connect nodes → dialog
  const handleConnect = useCallback((connection: Connection) => {
    const fromId = stripNodePrefix(connection.source ?? "", "agent-");
    const toId = stripNodePrefix(connection.target ?? "", "agent-");
    const from = allAgents?.find((a) => a.id === fromId);
    const to = allAgents?.find((a) => a.id === toId);
    if (!from || !to) return;
    setPendingConnection({ fromId, toId, fromName: from.name, toName: to.name });
  }, [allAgents]);

  // Delete edges via keyboard
  const handleEdgesDelete = useCallback((deletedEdges: Edge[]) => {
    const blocked: string[] = [];
    for (const edge of deletedEdges) {
      const rawId = stripNodePrefix(edge.id, "edge-");
      const edgeData = allEdges.find((e) => e.id === rawId);
      if (edgeData && lockedWorkflowIds.has(edgeData.workflow_id)) {
        blocked.push(rawId);
        continue;
      }
      void mutations.handleDeleteEdge(rawId);
    }
    if (blocked.length > 0) {
      addToast({
        type: "warning",
        title: "Удаление заблокировано",
        message: "Некоторые связи нельзя удалить: workflow используется активной задачей.",
      });
    }
  }, [mutations, allEdges, lockedWorkflowIds, addToast]);

  const isLoading = teamsLoading || agentsLoading || workflowsLoading;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <p className="text-gray-400 text-sm">Loading canvas...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-80px)]">
      <div className="flex items-center justify-between px-1 py-2">
        <h1 className="text-lg font-semibold text-gray-900">Teams & Workflows</h1>
        <div className="flex items-center gap-3">
          <WorkflowFilter
            workflows={allWorkflows}
            selectedId={selectedWorkflowId}
            onSelect={setSelectedWorkflowId}
          />
          {showCreateTeam ? (
            <CreateTeamForm
              onSubmit={(data) => {
                void mutations.handleCreateTeam(data);
                setShowCreateTeam(false);
              }}
              onCancel={() => setShowCreateTeam(false)}
            />
          ) : (
            <button
              className="text-sm text-blue-600 border border-blue-200 rounded px-3 py-1 hover:bg-blue-50"
              onClick={() => setShowCreateTeam(true)}
            >
              + Team
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-1 border rounded-lg overflow-hidden bg-gray-50">
        <div className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            minZoom={0.3}
            maxZoom={2}
            nodesDraggable
            nodesConnectable
            elementsSelectable
            onNodeClick={handleNodeClick}
            onEdgeClick={handleEdgeClick}
            onNodeDragStop={handleNodeDragStop}
            onConnect={handleConnect}
            onEdgesDelete={handleEdgesDelete}
            deleteKeyCode="Delete"
          >
            <MiniMap
              nodeColor={(node) => {
                if (node.type === "teamGroup") return "#dbeafe";
                return "#ffffff";
              }}
              className="!bg-gray-100"
            />
            <Controls showInteractive={false} />
            <Background gap={20} size={1} />
          </ReactFlow>
        </div>

        {panelSelection && allAgents && (
          <SidePanel
            selection={panelSelection}
            agents={allAgents}
            workflows={allWorkflows}
            workflowEdges={allEdges}
            lockedWorkflowIds={lockedWorkflowIds}
            onClose={() => setPanelSelection(null)}
            onUpdateAgent={(id, _teamId, data) => {
              void mutations.handleUpdateAgent(id, data);
            }}
            onDeleteAgent={(id) => {
              void mutations.handleDeleteAgent(id);
              setPanelSelection(null);
            }}
            onUpdateEdge={(edgeId, _workflowId, data) => {
              void mutations.handleUpdateEdge(edgeId, data);
            }}
            onDeleteEdge={(edgeId) => {
              void mutations.handleDeleteEdge(edgeId);
              setPanelSelection(null);
            }}
            onCreateEdge={(workflowId, fromAgentId, toAgentId) => {
              void mutations.handleCreateEdge(workflowId, {
                from_agent_id: fromAgentId,
                to_agent_id: toAgentId,
              });
            }}
            onUpdateWorkflow={(workflowId, data) => {
              void mutations.handleUpdateWorkflow(workflowId, data);
            }}
            onCreateWorkflow={(teamId, data) => {
              void mutations.handleCreateWorkflow(teamId, data);
            }}
          />
        )}
      </div>

      {createAgentTeamId && (
        <CreateAgentModal
          defaultName={`Agent ${(allAgents?.filter((a) => a.team_id === createAgentTeamId).length ?? 0) + 1}`}
          onSubmit={(data) => {
            void mutations.handleCreateAgent(createAgentTeamId, {
              ...data,
              role: "agent",
            });
            setCreateAgentTeamId(null);
          }}
          onClose={() => setCreateAgentTeamId(null)}
        />
      )}

      {pendingConnection && (
        <ConnectEdgeDialog
          workflows={allWorkflows}
          fromAgentName={pendingConnection.fromName}
          toAgentName={pendingConnection.toName}
          onSubmit={(workflowId, condition) => {
            void mutations.handleCreateEdge(workflowId, {
              from_agent_id: pendingConnection.fromId,
              to_agent_id: pendingConnection.toId,
              condition,
            });
            setPendingConnection(null);
          }}
          onCancel={() => setPendingConnection(null)}
        />
      )}
    </div>
  );
}
