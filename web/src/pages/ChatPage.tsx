import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getSession, stopSession } from "../api/sessions";
import { useChat } from "../hooks/useChat";
import type { ChatStatus } from "../hooks/useChat";
import { ChatWindow } from "../components/ChatWindow";

function StatusIndicator({ status }: { status: ChatStatus }) {
  const labels: Record<ChatStatus, string> = {
    connecting: "Connecting...",
    connected: "Ready",
    typing: "Agent is typing...",
    tool: "Using tool...",
    disconnected: "Disconnected",
  };

  const colors: Record<ChatStatus, string> = {
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

export function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const { data: session, isLoading, error: loadError } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => getSession(sessionId ?? ""),
    enabled: Boolean(sessionId),
  });

  const {
    messages,
    status,
    error: chatError,
    sendMessage,
    stopAgent,
  } = useChat(sessionId ?? "", session?.messages ?? []);

  async function handleStop() {
    stopAgent();
    if (sessionId) {
      await stopSession(sessionId);
    }
    navigate("/");
  }

  if (!sessionId) {
    return <p className="text-red-600">Missing session ID</p>;
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

  const isActive = status === "connected" || status === "typing" || status === "tool";

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <div className="flex items-center justify-between border-b px-4 py-3 bg-white">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-gray-900">Chat</h1>
          <StatusIndicator status={status} />
        </div>
        <button
          onClick={() => void handleStop()}
          disabled={status === "disconnected"}
          className="rounded border border-red-300 px-3 py-1 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
        >
          Stop
        </button>
      </div>

      {chatError && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-2 text-sm text-red-600">
          {chatError}
        </div>
      )}

      <ChatWindow messages={messages} />

      <ChatInput onSend={sendMessage} disabled={!isActive} />
    </div>
  );
}
