import { useCallback, useEffect, useRef } from "react";
import type { WsIncoming } from "../../types";
import type { ChatStatus } from "./chatState";
import { MAX_RECONNECT_ATTEMPTS, RECONNECT_DELAY_MS } from "./chatState";
import { isHandoffItem } from "../../types";
import type { ChatItem } from "../../types";

interface UseChatSocketOptions {
  sessionId: string;
  enabled: boolean;
  initializedRef: React.MutableRefObject<boolean>;
  onEvent: (event: WsIncoming) => void;
  setStatus: React.Dispatch<React.SetStateAction<ChatStatus>>;
  setError: React.Dispatch<React.SetStateAction<string | null>>;
  setItems: React.Dispatch<React.SetStateAction<ChatItem[]>>;
  resetPendingRefs: () => void;
}

interface UseChatSocketResult {
  wsRef: React.MutableRefObject<WebSocket | null>;
  stoppedRef: React.MutableRefObject<boolean>;
  reconnectTimer: React.MutableRefObject<ReturnType<typeof setTimeout> | null>;
}

export function useChatSocket(options: UseChatSocketOptions): UseChatSocketResult {
  const { sessionId, enabled, initializedRef, onEvent, setStatus, setError, setItems, resetPendingRefs } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stoppedRef = useRef(false);

  const connect = useCallback(() => {
    if (stoppedRef.current) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/api/ws/sessions/${sessionId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => {
      setStatus("connected");
      setError(null);
      reconnectCount.current = 0;
    };

    ws.onmessage = (e: MessageEvent) => {
      try {
        const data = JSON.parse(String(e.data)) as WsIncoming;
        onEvent(data);
      } catch {
        setError("Failed to parse server message");
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      setStatus("disconnected");
      resetPendingRefs();
      setItems((prev) => prev.filter((i) => {
        if (isHandoffItem(i)) return i.id !== "__sub_agent_streaming__";
        return i.id !== "__streaming__";
      }));
      if (!stoppedRef.current && reconnectCount.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectCount.current += 1;
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
      }
    };

    ws.onerror = () => {
      setError("WebSocket connection error");
    };
  }, [sessionId, onEvent, setStatus, setError, setItems, resetPendingRefs]);

  useEffect(() => {
    if (!enabled || !initializedRef.current) return;

    stoppedRef.current = false;
    connect();

    return () => {
      reconnectCount.current = MAX_RECONNECT_ATTEMPTS;
      if (reconnectTimer.current !== null) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
      wsRef.current?.close();
    };
  }, [enabled, connect, initializedRef]);

  return { wsRef, stoppedRef, reconnectTimer };
}
