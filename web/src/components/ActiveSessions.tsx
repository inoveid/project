import type { SessionListItem } from "../types";

interface ActiveSessionsProps {
  sessions: SessionListItem[];
  onOpenChat: (sessionId: string) => void;
}

export function ActiveSessions({ sessions, onOpenChat }: ActiveSessionsProps) {
  if (sessions.length === 0) {
    return (
      <p className="text-sm text-gray-400">No active sessions</p>
    );
  }

  return (
    <div className="space-y-2">
      {sessions.map((session) => (
        <div
          key={session.id}
          className="flex items-center justify-between bg-white rounded-lg border p-3"
        >
          <div>
            <span className="text-sm font-medium text-gray-900">
              {session.agent_name}
            </span>
            <p className="text-xs text-gray-400">
              Started {new Date(session.created_at).toLocaleString()}
            </p>
          </div>
          <button
            onClick={() => onOpenChat(session.id)}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
          >
            Open Chat
          </button>
        </div>
      ))}
    </div>
  );
}
