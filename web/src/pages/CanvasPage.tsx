import { useMemo, useState } from "react";
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  type NodeTypes,
  type EdgeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useTeams } from "../hooks/useTeams";
import { useAllAgents } from "../hooks/useAgents";
import { useCanvasData } from "./useCanvasData";
import { AgentNode } from "../components/canvas/AgentNode";
import { TeamGroupNode } from "../components/canvas/TeamGroupNode";
import { WorkflowEdgeComponent } from "../components/canvas/WorkflowEdge";
import { WorkflowFilter } from "../components/canvas/WorkflowFilter";
import {
  buildCanvasLayout,
  buildWorkflowColorMap,
  applyWorkflowFilter,
} from "../components/canvas/canvasUtils";

const nodeTypes: NodeTypes = {
  agentNode: AgentNode,
  teamGroup: TeamGroupNode,
};

const edgeTypes: EdgeTypes = {
  workflowEdge: WorkflowEdgeComponent,
};

export function CanvasPage() {
  const { data: teams, isLoading: teamsLoading } = useTeams();
  const { data: allAgents, isLoading: agentsLoading } = useAllAgents();
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);

  const { allWorkflows, allEdges, isLoading: workflowsLoading } = useCanvasData(teams);

  const agentsByTeam = useMemo(() => {
    const map = new Map<string, NonNullable<typeof allAgents>>();
    if (!allAgents) return map;
    for (const agent of allAgents) {
      const existing = map.get(agent.team_id) ?? [];
      existing.push(agent);
      map.set(agent.team_id, existing);
    }
    return map;
  }, [allAgents]);

  const workflowColorMap = useMemo(
    () => buildWorkflowColorMap(allWorkflows),
    [allWorkflows],
  );

  const activeAgentIds = useMemo(() => new Set<string>(), []);

  const { nodes, edges: rawEdges } = useMemo(() => {
    if (!teams) return { nodes: [], edges: [] };
    return buildCanvasLayout(
      teams,
      agentsByTeam,
      allWorkflows,
      allEdges,
      workflowColorMap,
      activeAgentIds,
    );
  }, [teams, agentsByTeam, allWorkflows, allEdges, workflowColorMap, activeAgentIds]);

  const edges = useMemo(
    () => applyWorkflowFilter(rawEdges, selectedWorkflowId, allEdges, workflowColorMap),
    [rawEdges, selectedWorkflowId, allEdges, workflowColorMap],
  );

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
          <button
            disabled
            className="text-sm text-gray-400 border border-gray-200 rounded px-3 py-1 cursor-not-allowed"
            title="Available in edit mode"
          >
            + Team
          </button>
        </div>
      </div>

      <div className="flex-1 border rounded-lg overflow-hidden bg-gray-50">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          minZoom={0.3}
          maxZoom={2}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          proOptions={{ hideAttribution: true }}
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
    </div>
  );
}
