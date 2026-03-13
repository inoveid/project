import type { HandoffItem } from "../types";
import { ToolUseBlock } from "./ToolUseBlock";

interface HandoffBlockProps {
  item: HandoffItem;
}

export function HandoffBlock({ item }: HandoffBlockProps) {
  if (item.itemType === "activity") {
    return (
      <div className="flex items-center gap-2 py-2">
        <div className="flex items-center gap-1.5 bg-gray-100 rounded-2xl px-4 py-2">
          <div className="flex gap-1">
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
          <span className="text-xs text-gray-500 ml-1">{item.content}</span>
        </div>
      </div>
    );
  }

  if (item.itemType === "handoff_cycle") {
    return (
      <div className="my-2 flex items-center gap-2 text-amber-600 text-sm">
        <span>⚠</span>
        <span>{item.content}</span>
      </div>
    );
  }

  if (item.itemType === "approval_required") {
    return (
      <div className="my-3">
        <div className="flex items-center gap-2 text-xs text-amber-600 uppercase tracking-wide">
          <div className="flex-1 h-px bg-amber-200" />
          <span>⏸ {item.fromAgent} → {item.toAgent} (awaiting approval)</span>
          <div className="flex-1 h-px bg-amber-200" />
        </div>
      </div>
    );
  }

  if (item.itemType === "handoff_start") {
    return (
      <div className="my-3">
        <div className="flex items-center gap-2 text-xs text-gray-400 uppercase tracking-wide">
          <div className="flex-1 h-px bg-gray-200" />
          <span>↓ {item.fromAgent} → {item.toAgent}</span>
          <div className="flex-1 h-px bg-gray-200" />
        </div>
      </div>
    );
  }

  // Fallback for any other item type
  return null;
}
