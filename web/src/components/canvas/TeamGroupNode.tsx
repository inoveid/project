import type { NodeProps } from "@xyflow/react";
import { getNodeData } from "./types";
import type { TeamGroupNodeData } from "./types";

export type { TeamGroupNodeData } from "./types";

export function TeamGroupNode({ data }: NodeProps) {
  const { team, agentCount } = getNodeData<TeamGroupNodeData>(data);

  return (
    <div className="w-full h-full bg-blue-50/50 border-2 border-blue-200 rounded-xl">
      <div className="flex items-center justify-between px-3 py-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-gray-800">{team.name}</h3>
          <span className="text-xs text-gray-500">
            {agentCount} {agentCount === 1 ? "agent" : "agents"}
          </span>
        </div>
        <button
          disabled
          className="text-xs text-gray-400 border border-gray-200 rounded px-2 py-0.5 cursor-not-allowed"
          title="Available in edit mode"
        >
          + Agent
        </button>
      </div>
    </div>
  );
}
