import { useState } from "react";
import type { ToolUse } from "../types";

interface ToolUseBlockProps {
  toolUse: ToolUse;
}

export function ToolUseBlock({ toolUse }: ToolUseBlockProps) {
  const [expanded, setExpanded] = useState(false);

  const inputPreview = JSON.stringify(toolUse.tool_input).slice(0, 80);

  return (
    <div className="my-1 rounded border border-gray-200 bg-gray-50 text-sm">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-gray-100"
      >
        <span className="text-gray-400">{expanded ? "▼" : "▶"}</span>
        <span className="font-mono font-medium text-gray-700">
          {toolUse.tool_name}
        </span>
        {!expanded && (
          <span className="truncate text-gray-400">{inputPreview}</span>
        )}
      </button>
      {expanded && (
        <pre className="overflow-x-auto border-t border-gray-200 bg-gray-100 px-3 py-2 font-mono text-xs text-gray-600">
          {JSON.stringify(toolUse.tool_input, null, 2)}
        </pre>
      )}
    </div>
  );
}
