import { BaseEdge, EdgeLabelRenderer, getBezierPath } from "@xyflow/react";
import type { EdgeProps } from "@xyflow/react";

interface WorkflowEdgeData {
  condition: string | null;
  requiresApproval: boolean;
  color: string;
  [key: string]: unknown;
}

export function WorkflowEdgeComponent(props: EdgeProps) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, style, markerEnd, data } = props;
  const { condition, requiresApproval, color } = (data ?? {}) as WorkflowEdgeData;

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  const hasLabel = condition || requiresApproval;

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{ ...style, stroke: color, strokeWidth: 2 }}
      />
      {hasLabel && (
        <EdgeLabelRenderer>
          <div
            className="absolute flex items-center gap-1 bg-white border border-gray-200 rounded px-1.5 py-0.5 shadow-sm pointer-events-auto"
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            }}
          >
            <span className="text-[10px]" title={requiresApproval ? "Requires approval" : "Auto"}>
              {requiresApproval ? "\uD83D\uDD12" : "\u26A1"}
            </span>
            {condition && (
              <span className="text-[10px] text-gray-600 max-w-[120px] truncate">{condition}</span>
            )}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
