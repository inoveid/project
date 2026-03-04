import { useQuery } from "@tanstack/react-query";
import { getSessions } from "../api/sessions";
import type { SessionListItem } from "../types";

interface SessionListProps {
  onSelectSession: (sessionId: string) => void;
  onOpenSide?: (sessionId: string) => void;
  activeSessionIds?: string[];
}

function SessionItem({
  session,
  isActive,
  onSelect,
  onOpenSide,
}: {
  session: SessionListItem;
  isActive: boolean;
  onSelect: () => void;
  onOpenSide?: () => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => { if (e.key === "Enter") onSelect(); }}
      className={`block w-full text-left rounded border p-3 transition-colors cursor-pointer ${
        isActive
          ? "border-blue-400 bg-blue-50"
          : "hover:bg-gray-50"
      }`}
      data-session-id={session.id}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">
          {session.id.slice(0, 8)}...
        </span>
        <span
          className={`text-xs px-2 py-0.5 rounded ${
            session.status === "active"
              ? "bg-green-100 text-green-700"
              : "bg-gray-100 text-gray-500"
          }`}
        >
          {session.status}
        </span>
      </div>
      <p className="text-xs text-gray-400 mt-1">
        {new Date(session.created_at).toLocaleString()}
      </p>
      {onOpenSide && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onOpenSide();
          }}
          className="mt-2 text-xs text-blue-600 hover:text-blue-800"
        >
          Open side-by-side
        </button>
      )}
    </div>
  );
}

export function SessionList({
  onSelectSession,
  onOpenSide,
  activeSessionIds = [],
}: SessionListProps) {
  const { data: sessions, isLoading } = useQuery({
    queryKey: ["sessions"],
    queryFn: getSessions,
    refetchInterval: 10_000,
  });

  if (isLoading) {
    return (
      <div className="p-4 text-sm text-gray-400">Loading sessions...</div>
    );
  }

  if (!sessions || sessions.length === 0) {
    return (
      <div className="p-4 text-sm text-gray-400">No active sessions</div>
    );
  }

  return (
    <div className="p-3 space-y-2">
      <h2 className="text-sm font-semibold text-gray-900 mb-2">
        Sessions
      </h2>
      {sessions.map((session) => (
        <SessionItem
          key={session.id}
          session={session}
          isActive={activeSessionIds.includes(session.id)}
          onSelect={() => onSelectSession(session.id)}
          onOpenSide={onOpenSide ? () => onOpenSide(session.id) : undefined}
        />
      ))}
    </div>
  );
}
