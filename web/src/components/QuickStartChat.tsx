import { useState } from "react";
import { useAllAgents } from "../hooks/useAgents";
import { useAuthStatus } from "../hooks/useAuth";
import { useCreateSession } from "../hooks/useSessions";

interface QuickStartChatProps {
  onSessionCreated: (sessionId: string) => void;
}

export function QuickStartChat({ onSessionCreated }: QuickStartChatProps) {
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const { data: agents } = useAllAgents();
  const { data: authStatus } = useAuthStatus();
  const createSession = useCreateSession();
  const isAuthenticated = authStatus?.logged_in ?? false;

  function handleStart() {
    if (!selectedAgentId) return;
    createSession.mutate(selectedAgentId, {
      onSuccess: (session) => {
        onSessionCreated(session.id);
        setSelectedAgentId("");
      },
    });
  }

  if (!agents || agents.length === 0) {
    return (
      <p className="text-sm text-gray-400">
        No agents available. Create a team with agents first.
      </p>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <select
        value={selectedAgentId}
        onChange={(e) => setSelectedAgentId(e.target.value)}
        className="border rounded px-3 py-2 text-sm text-gray-700 bg-white"
      >
        <option value="">Select agent...</option>
        {agents.map((agent) => (
          <option key={agent.id} value={agent.id}>
            {agent.name} — {agent.role}
          </option>
        ))}
      </select>
      <button
        onClick={handleStart}
        disabled={!selectedAgentId || createSession.isPending || !isAuthenticated}
        title={!isAuthenticated ? "Claude authentication required" : undefined}
        className="bg-green-600 text-white px-4 py-2 rounded text-sm hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {createSession.isPending ? "Starting..." : "Start Chat"}
      </button>
      {!isAuthenticated && (
        <span className="text-xs text-red-500">Auth required</span>
      )}
    </div>
  );
}
