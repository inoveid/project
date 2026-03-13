/**
 * SubAgentBlock — renders a sub-agent spawn/completion item in the chat.
 * Shows role badge, task preview, and status (running/done/error).
 */

interface SubAgentBlockProps {
  content: string;
  agentName: string;
}

export function SubAgentBlock({ content, agentName }: SubAgentBlockProps) {
  const isDone = content.startsWith("\u2713");
  const isError = content.startsWith("\u2717");
  const isRunning = content.startsWith("\u2192");

  const statusColor = isDone
    ? "bg-green-50 border-green-200"
    : isError
      ? "bg-red-50 border-red-200"
      : "bg-purple-50 border-purple-200";

  const dotColor = isDone
    ? "bg-green-500"
    : isError
      ? "bg-red-500"
      : "bg-purple-500 animate-pulse";

  return (
    <div className={`flex items-start gap-2 px-3 py-2 rounded-md border text-xs ${statusColor}`}>
      <span className={`mt-1 inline-block w-2 h-2 rounded-full ${dotColor} flex-shrink-0`} />
      <div className="flex-1 min-w-0">
        <span className="font-medium text-gray-700">{agentName}</span>
        <p className="text-gray-600 mt-0.5 break-words">
          {content.replace(/^[\u2192\u2713\u2717]\s*/, "").replace(new RegExp(`^${agentName}\\s*`), "")}
        </p>
      </div>
    </div>
  );
}
