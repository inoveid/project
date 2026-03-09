import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useChat } from "../hooks/chat";
import { useSystemAgent } from "../hooks/useSystemAgent";
import { useAuthStatus } from "../hooks/useAuthStatus";
import { getSession } from "../api/sessions";
import { MiniChatWindow } from "./MiniChatWindow";

function DisabledChatButton({ tooltip }: { tooltip: string }) {
  return (
    <div className="fixed bottom-6 right-6 z-50">
      <button
        disabled
        title={tooltip}
        aria-label={tooltip}
        className="bg-gray-400 text-white rounded-full w-14 h-14 flex items-center justify-center shadow-lg cursor-not-allowed text-xl"
      >
        💬
      </button>
    </div>
  );
}

function ChatToggleButton({
  isOpen,
  onClick,
}: {
  isOpen: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={isOpen ? "Свернуть чат" : "Открыть чат"}
      aria-label={isOpen ? "Свернуть чат" : "Открыть чат"}
      className="bg-blue-600 text-white rounded-full w-14 h-14 flex items-center justify-center shadow-lg hover:bg-blue-700 transition-colors text-xl"
    >
      {isOpen ? "✕" : "💬"}
    </button>
  );
}

export function GlobalChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const { authStatus } = useAuthStatus();
  const { sessionId, isReady, resetSession } = useSystemAgent();

  const { data: session } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => getSession(sessionId!),
    enabled: Boolean(sessionId) && isReady && isOpen,
  });

  const chat = useChat(
    sessionId ?? "",
    session?.messages ?? [],
    isReady && isOpen && Boolean(sessionId),
  );

  const isDisabled = !authStatus?.logged_in;

  if (isDisabled) {
    return <DisabledChatButton tooltip="Требуется авторизация в Claude" />;
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
      {isOpen && isReady && (
        <div className="fixed bottom-24 right-6 z-50">
          <MiniChatWindow
            title="Assistant"
            chat={chat}
            onClose={() => setIsOpen(false)}
            onClear={resetSession}
          />
        </div>
      )}
      <ChatToggleButton isOpen={isOpen} onClick={() => setIsOpen((o) => !o)} />
    </div>
  );
}
