import { BaseEdge, EdgeLabelRenderer, getBezierPath } from "@xyflow/react";
import type { EdgeProps } from "@xyflow/react";
import { getNodeData } from "./types";
import type { WorkflowEdgeData } from "./types";

export function WorkflowEdgeComponent(props: EdgeProps) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, style, markerEnd, data } = props;
  const { condition, requiresApproval, color } = getNodeData<WorkflowEdgeData>(data ?? {});

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
            <span
              className="text-[10px]"
              title={requiresApproval ? "Requires approval" : "Auto"}
              aria-label={requiresApproval ? "Requires approval" : "Auto"}
            >
              {requiresApproval ? (
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
              ) : (
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                </svg>
              )}
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
