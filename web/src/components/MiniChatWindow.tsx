import { useState } from "react";
import type { UseChatResult } from "../hooks/chat";
import { ChatWindow } from "./ChatWindow";

interface MiniChatWindowProps {
  title: string;
  chat: UseChatResult;
  onClose: () => void;
  onClear: () => void;
}

function MiniChatInput({
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
    <form onSubmit={handleSubmit} className="flex gap-1 border-t p-2 bg-white">
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Напишите сообщение..."
        disabled={disabled}
        className="flex-1 rounded border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none disabled:bg-gray-100"
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        →
      </button>
    </form>
  );
}

export function MiniChatWindow({ title, chat, onClose, onClear }: MiniChatWindowProps) {
  const { items, status, error, sendMessage } = chat;
  const canSend = status === "connected";

  function handleClear() {
    if (window.confirm("Очистить историю чата?")) {
      onClear();
    }
  }

  return (
    <div className="flex flex-col bg-white rounded-lg shadow-2xl border border-gray-200 overflow-hidden w-[400px] h-[560px]">
      <div className="flex items-center justify-between px-4 py-3 bg-white border-b">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-900">{title}</span>
          {status === "typing" && (
            <span className="text-xs text-blue-600">печатает...</span>
          )}
          {status === "connected" && (
            <span className="text-xs text-green-600">●</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleClear}
            title="Очистить контекст"
            className="rounded p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 text-xs"
          >
            🗑
          </button>
          <button
            onClick={onClose}
            title="Свернуть"
            className="rounded p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 text-sm leading-none"
          >
            ✕
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border-b border-red-200 px-3 py-1.5 text-xs text-red-600">
          {error}
        </div>
      )}

      <ChatWindow items={items} />

      <MiniChatInput onSend={sendMessage} disabled={!canSend} />
    </div>
  );
}
