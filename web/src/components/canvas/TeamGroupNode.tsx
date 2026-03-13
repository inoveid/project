import type { NodeProps } from "@xyflow/react";
import { getNodeData } from "./types";
import type { TeamGroupNodeData } from "./types";

export type { TeamGroupNodeData } from "./types";

function getBorderClass(data: TeamGroupNodeData): string {
  if (data.validationIssues.some((i) => i.type === "error"))
    return "border-red-400";
  if (data.isLocked) return "border-amber-400";
  return "border-blue-200";
}

export function TeamGroupNode({ data }: NodeProps) {
  const nodeData = getNodeData<TeamGroupNodeData>(data);
  const { team, agentCount, onAddAgent, onAddWorkflow, validationIssues, isLocked } = nodeData;
  const borderClass = getBorderClass(nodeData);
  const infoIssues = validationIssues.filter((i) => i.type === "info");

  return (
    <div className={`w-full h-full bg-blue-50/50 border-2 ${borderClass} rounded-xl`}>
      <div className="flex items-center justify-between px-3 py-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-gray-800">{team.name}</h3>
          <span className="text-xs text-gray-500">
            {agentCount} {agentCount === 1 ? "agent" : "agents"}
          </span>
          {isLocked && (
            <span
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-700"
              title="Workflow is being used by an active task"
              data-testid="lock-badge"
            >
              In progress
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            className="text-xs text-blue-600 border border-blue-200 rounded px-2 py-0.5 hover:bg-blue-100 nopan nodrag"
            onClick={(e) => { e.stopPropagation(); onAddAgent?.(team.id); }}
          >
            Agents
          </button>
          <button
            className="text-xs text-blue-600 border border-blue-200 rounded px-2 py-0.5 hover:bg-blue-100 nopan nodrag"
            onClick={(e) => { e.stopPropagation(); onAddWorkflow?.(team.id); }}
          >
            Workflows
          </button>
        </div>
      </div>
      {infoIssues.length > 0 && (
        <div className="px-3 pb-1">
          {infoIssues.map((issue, idx) => (
            <p key={idx} className="text-[11px] text-gray-400 italic">
              {issue.message}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
