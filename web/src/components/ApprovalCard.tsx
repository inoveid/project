import { useState } from "react";
import type { ApprovalRequest } from "../types";

interface ApprovalCardProps {
  approval: ApprovalRequest;
  onApprove: () => void;
  onRefine: (comment: string) => void;
}

export function ApprovalCard({ approval, onApprove, onRefine }: ApprovalCardProps) {
  const { fromAgent, toAgent, task, steps = [] } = approval;
  const [comment, setComment] = useState("");

  const handleRefine = () => {
    const text = comment.trim();
    if (!text) return;
    setComment("");
    onRefine(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleRefine();
    }
  };

  // Build ordered progress entries from steps
  const progressEntries: { agent: string; summary?: string; status: "done" | "current" | "pending" }[] = [];
  for (const s of steps) {
    progressEntries.push({ agent: s.agent, summary: s.summary, status: "done" });
  }
  const toAgentInSteps = steps.some((s) => s.agent === toAgent);
  if (!toAgentInSteps) {
    progressEntries.push({ agent: toAgent, status: "current" });
  } else {
    for (let i = progressEntries.length - 1; i >= 0; i--) {
      if (progressEntries[i]!.agent === toAgent) {
        progressEntries[i]!.status = "current";
        break;
      }
    }
  }

  return (
    <div className="border-t border-amber-200 bg-amber-50/80 px-4 py-4 space-y-3">
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className="text-amber-500 text-lg">⏸</span>
        <span className="text-sm font-semibold text-amber-900">Передача задачи</span>
      </div>

      {/* Transfer direction */}
      <div className="flex items-center gap-2 text-sm">
        <span className="font-medium text-gray-800">{fromAgent}</span>
        <span className="text-gray-400">→</span>
        <span className="font-medium text-gray-800">{toAgent}</span>
      </div>

      {/* Progress tracker */}
      {progressEntries.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Прогресс</p>
          <div className="space-y-1">
            {progressEntries.map((entry, idx) => (
              <div key={`${entry.agent}-${idx}`} className="flex items-start gap-2">
                <span className="mt-0.5 text-xs shrink-0">
                  {entry.status === "done" ? "✅" : entry.status === "current" ? "⏳" : "○"}
                </span>
                <div className="min-w-0">
                  <span className={`text-xs font-medium ${entry.status === "done" ? "text-gray-700" : entry.status === "current" ? "text-amber-700" : "text-gray-400"}`}>
                    {entry.agent}
                  </span>
                  {entry.status === "done" && entry.summary && (
                    <p className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">{entry.summary}</p>
                  )}
                  {entry.status === "current" && (
                    <p className="text-[11px] text-amber-600 mt-0.5">ожидает одобрения</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Handoff message */}
      {task && (
        <div className="bg-white/60 rounded border border-amber-100 px-3 py-2">
          <p className="text-[11px] font-medium text-gray-500 mb-1">Сообщение</p>
          <p className="text-xs text-gray-700 line-clamp-3">{task}</p>
        </div>
      )}

      {/* Comment input */}
      <div className="flex gap-2">
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Комментарий для агента..."
          rows={2}
          className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-transparent"
        />
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={onApprove}
          className="flex-1 rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 transition-colors"
        >
          Одобрить
        </button>
        <button
          onClick={handleRefine}
          disabled={!comment.trim()}
          className="flex-1 rounded border border-amber-400 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-800 hover:bg-amber-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Написать
        </button>
      </div>
    </div>
  );
}
