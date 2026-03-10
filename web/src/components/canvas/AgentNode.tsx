import { Handle, Position } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";
import { getNodeData } from "./types";
import type { AgentNodeData } from "./types";

export type { AgentNodeData } from "./types";

function getValidationBorderClass(
  issues: AgentNodeData["validationIssues"],
): string {
  if (issues.some((i) => i.type === "error")) return "border-red-500 border-2";
  if (issues.some((i) => i.type === "warning"))
    return "border-yellow-400 border-2";
  return "border-gray-200";
}

function getValidationTooltip(
  issues: AgentNodeData["validationIssues"],
): string {
  return issues.map((i) => i.message).join("\n");
}

export function AgentNode({ data }: NodeProps) {
  const { agent, isStart, isEnd, isActive, validationIssues } =
    getNodeData<AgentNodeData>(data);

  const borderClass = getValidationBorderClass(validationIssues);
  const tooltip = getValidationTooltip(validationIssues);
  const hasIssues = validationIssues.length > 0;

  return (
    <div
      className={`bg-white ${borderClass} rounded-lg shadow-sm px-3 py-2 min-w-[180px]`}
      title={hasIssues ? tooltip : undefined}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-gray-400 !w-2 !h-2"
      />

      <div className="flex items-center gap-1.5 mb-1">
        {isActive && (
          <span
            className="inline-block w-2 h-2 rounded-full bg-green-500 animate-pulse"
            title="Active"
          />
        )}
        <span className="font-semibold text-sm text-gray-900 truncate">
          {agent.name}
        </span>
        {hasIssues && (
          <span
            className="inline-block w-3.5 h-3.5 text-[10px] leading-[14px] text-center rounded-full bg-yellow-100 text-yellow-700"
            title={tooltip}
          >
            !
          </span>
        )}
      </div>

      {agent.description && (
        <p className="text-xs text-gray-500 truncate mb-1">
          {agent.description}
        </p>
      )}

      <div className="flex gap-1">
        {isStart && (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-100 text-green-700">
            Start
          </span>
        )}
        {isEnd && (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-100 text-red-700">
            End
          </span>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-gray-400 !w-2 !h-2"
      />
    </div>
  );
}
