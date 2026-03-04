import { useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { SessionList } from "../components/SessionList";
import { ChatPanel } from "../components/ChatPanel";

export function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [sidePanelId, setSidePanelId] = useState<string | null>(null);

  const handleSelectSession = useCallback(
    (id: string) => {
      navigate(`/chat/${id}`);
    },
    [navigate],
  );

  const handleOpenSide = useCallback(
    (id: string) => {
      if (id === sessionId) return;
      setSidePanelId(id);
    },
    [sessionId],
  );

  const handleCloseSide = useCallback(() => {
    setSidePanelId(null);
  }, []);

  if (!sessionId) {
    return <p className="text-red-600 p-4">Missing session ID</p>;
  }

  const activeIds = sidePanelId
    ? [sessionId, sidePanelId]
    : [sessionId];

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      <aside className="w-64 shrink-0 border-r bg-gray-50 overflow-y-auto">
        <SessionList
          onSelectSession={handleSelectSession}
          onOpenSide={handleOpenSide}
          activeSessionIds={activeIds}
        />
      </aside>

      <div className="flex flex-1 min-w-0">
        <div className={sidePanelId ? "w-1/2" : "w-full"}>
          <ChatPanel sessionId={sessionId} />
        </div>

        {sidePanelId && (
          <div className="w-1/2">
            <ChatPanel
              sessionId={sidePanelId}
              onClose={handleCloseSide}
              showClose
            />
          </div>
        )}
      </div>
    </div>
  );
}
