import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSystemAgent } from "../api/agents";
import { createSession, getSession } from "../api/sessions";

const SYSTEM_SESSION_KEY = "system_agent_session_id";

export interface UseSystemAgentResult {
  sessionId: string | null;
  isReady: boolean;
  resetSession: () => void;
}

export function useSystemAgent(): UseSystemAgentResult {
  const [sessionId, setSessionId] = useState<string | null>(
    () => localStorage.getItem(SYSTEM_SESSION_KEY),
  );
  const [isReady, setIsReady] = useState(false);
  const [resetKey, setResetKey] = useState(0);

  const { data: systemAgent } = useQuery({
    queryKey: ["agents", "system"],
    queryFn: getSystemAgent,
  });

  useEffect(() => {
    if (!systemAgent) return;

    let cancelled = false;

    async function initSession() {
      const storedId = localStorage.getItem(SYSTEM_SESSION_KEY);

      if (storedId) {
        try {
          await getSession(storedId);
          if (!cancelled) {
            setSessionId(storedId);
            setIsReady(true);
          }
          return;
        } catch {
          localStorage.removeItem(SYSTEM_SESSION_KEY);
        }
      }

      try {
        const session = await createSession(systemAgent!.id);
        localStorage.setItem(SYSTEM_SESSION_KEY, session.id);
        if (!cancelled) {
          setSessionId(session.id);
          setIsReady(true);
        }
      } catch {
        // Session creation failed; widget remains unready
      }
    }

    setIsReady(false);
    void initSession();

    return () => {
      cancelled = true;
    };
  }, [systemAgent, resetKey]);

  function resetSession() {
    localStorage.removeItem(SYSTEM_SESSION_KEY);
    setSessionId(null);
    setIsReady(false);
    setResetKey((k) => k + 1);
  }

  return { sessionId, isReady, resetSession };
}
