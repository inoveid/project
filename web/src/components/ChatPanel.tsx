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
  };

  const colors: Record<ChatStatus, string> = {
    idle: "text-gray-400",
    connecting: "text-yellow-600",
    connected: "text-green-600",
    typing: "text-blue-600",
    tool: "text-purple-600",
    disconnected: "text-red-600",
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
    messages,
    status,
    error: chatError,
    sendMessage,
    stopAgent,
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

      <ChatWindow messages={messages} />

      <ChatInput onSend={sendMessage} disabled={!canSend} />
    </div>
  );
}
