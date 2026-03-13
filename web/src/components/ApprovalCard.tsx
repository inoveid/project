import type { ApprovalRequest } from "../types";

interface ApprovalCardProps {
  approval: ApprovalRequest;
  onApprove: () => void;
  onReject: () => void;
}

export function ApprovalCard({ approval, onApprove, onReject }: ApprovalCardProps) {
  const { fromAgent, toAgent, task, steps = [] } = approval;

  // Build ordered progress entries from steps, avoiding duplicate agent rows
  // Each step is shown once; if toAgent already appeared, mark the last occurrence as current
  const progressEntries: { agent: string; summary?: string; status: "done" | "current" | "pending" }[] = [];
  for (const s of steps) {
    progressEntries.push({ agent: s.agent, summary: s.summary, status: "done" });
  }
  // If toAgent is not yet in steps, add as current
  const toAgentInSteps = steps.some((s) => s.agent === toAgent);
  if (!toAgentInSteps) {
    progressEntries.push({ agent: toAgent, status: "current" });
  } else {
    // Mark the last occurrence of toAgent as current (it's being handed back)
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

      {/* Actions */}
      <div className="flex gap-2 pt-1">
        <button
          onClick={onApprove}
          className="flex-1 rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 transition-colors"
        >
          Одобрить
        </button>
        <button
          onClick={onReject}
          className="flex-1 rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Отклонить
        </button>
      </div>
    </div>
  );
}
