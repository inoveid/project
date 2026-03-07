import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getSession, stopSession } from "../api/sessions";
import { useChat } from "../hooks/useChat";
import type { ChatStatus } from "../hooks/useChat";
import { ChatWindow } from "./ChatWindow";

function StatusIndicator({ status }: { status: ChatStatus }) {
  const labels: Record<ChatStatus, string> = {
    idle: "Loading...",
    connecting: "Connecting...",
    connected: "Ready",
    typing: "Agent is typing...",
    tool: "Using tool...",
    disconnected: "Disconnected",
    awaiting_approval: "Waiting for approval...",
  };

  const colors: Record<ChatStatus, string> = {
    idle: "text-gray-400",
    connecting: "text-yellow-600",
    connected: "text-green-600",
    typing: "text-blue-600",
    tool: "text-purple-600",
    disconnected: "text-red-600",
    awaiting_approval: "text-amber-600",
  };

  return (
    <span className={`text-sm ${colors[status]}`}>{labels[status]}</span>
  );
}

function ChatInput({
  onSend,
  disabled,
}: {
  onSend: (content: string) => void;
  disabled: boolean;
}) {
  const [text, setText] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText("");
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 border-t p-4 bg-white">
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type a message..."
        disabled={disabled}
        className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:bg-gray-100"
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Send
      </button>
    </form>
  );
}

function ApprovalBanner({
  fromAgent,
  toAgent,
  onApprove,
  onReject,
}: {
  fromAgent: string;
  toAgent: string;
  onApprove: () => void;
  onReject: () => void;
}) {
  return (
    <div className="border-t border-amber-200 bg-amber-50 px-4 py-3">
      <p className="text-sm text-amber-800 mb-2">
        <span className="font-medium">{fromAgent}</span> wants to hand off to{" "}
        <span className="font-medium">{toAgent}</span>. Approve?
      </p>
      <div className="flex gap-2">
        <button
          onClick={onApprove}
          className="rounded bg-green-600 px-4 py-1.5 text-sm text-white hover:bg-green-700"
        >
          Approve
        </button>
        <button
          onClick={onReject}
          className="rounded border border-gray-300 px-4 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
        >
          Reject
        </button>
      </div>
    </div>
  );
}

interface ChatPanelProps {
  sessionId: string;
  onClose?: () => void;
  showClose?: boolean;
}

export function ChatPanel({ sessionId, onClose, showClose }: ChatPanelProps) {
  const queryClient = useQueryClient();
  const { data: session, isLoading, error: loadError } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => getSession(sessionId),
    enabled: Boolean(sessionId),
  });

  const sessionLoaded = Boolean(session);

  const {
    items,
    status,
    error: chatError,
    pendingApproval,
    sendMessage,
    stopAgent,
    approveHandoff,
    rejectHandoff,
  } = useChat(sessionId, session?.messages ?? [], sessionLoaded);

  async function handleStop() {
    stopAgent();
    await stopSession(sessionId);
    void queryClient.invalidateQueries({ queryKey: ["sessions"] });
  }

  if (isLoading) {
    return <p className="text-gray-500 p-4">Loading session...</p>;
  }

  if (loadError) {
    return (
      <p className="text-red-600 p-4">
        Failed to load session: {loadError.message}
      </p>
    );
  }

  const canSend = status === "connected";

  return (
    <div className="flex h-full flex-col border-l first:border-l-0">
      <div className="flex items-center justify-between border-b px-4 py-3 bg-white">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold text-gray-900">
            {sessionId.slice(0, 8)}...
          </h2>
          <StatusIndicator status={status} />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => void handleStop()}
            disabled={status === "disconnected" || status === "idle"}
            className="rounded border border-red-300 px-3 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-50"
          >
            Stop
          </button>
          {showClose && onClose && (
            <button
              onClick={onClose}
              className="rounded border border-gray-300 px-3 py-1 text-xs text-gray-600 hover:bg-gray-50"
            >
              Close
            </button>
          )}
        </div>
      </div>

      {chatError && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-2 text-sm text-red-600">
          {chatError}
        </div>
      )}

      <ChatWindow items={items} />

      {pendingApproval ? (
        <ApprovalBanner
          fromAgent={pendingApproval.fromAgent}
          toAgent={pendingApproval.toAgent}
          onApprove={approveHandoff}
          onReject={rejectHandoff}
        />
      ) : (
        <ChatInput onSend={sendMessage} disabled={!canSend} />
      )}
    </div>
  );
}
