import { useCallback, useEffect, useRef } from "react";
import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type { WsIncoming } from "../../types";
import type { ChatStatus } from "./chatState";
import { MAX_RECONNECT_ATTEMPTS, RECONNECT_BASE_DELAY_MS } from "./chatState";

interface UseChatSocketOptions {
  sessionId: string;
  enabled: boolean;
  initializedRef: MutableRefObject<boolean>;
  onEvent: (event: WsIncoming) => void;
  onDisconnect: () => void;
  setStatus: Dispatch<SetStateAction<ChatStatus>>;
  setError: Dispatch<SetStateAction<string | null>>;
}

interface UseChatSocketResult {
  send: (data: string) => void;
  stop: () => void;
  isOpen: () => boolean;
}

export function useChatSocket(options: UseChatSocketOptions): UseChatSocketResult {
  const { sessionId, enabled, initializedRef, onEvent, onDisconnect, setStatus, setError } = options;

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
      onDisconnect();
      if (!stoppedRef.current && reconnectCount.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectCount.current += 1;
        // Exponential backoff: 1s, 2s, 4s, 8s, ... capped at 30s
        const delay = Math.min(
          RECONNECT_BASE_DELAY_MS * Math.pow(2, reconnectCount.current - 1),
          30000,
        );
        reconnectTimer.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      setError("WebSocket connection error");
    };
  }, [sessionId, onEvent, onDisconnect, setStatus, setError]);

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

  const send = useCallback((data: string) => {
    wsRef.current?.send(data);
  }, []);

  const stop = useCallback(() => {
    stoppedRef.current = true;
    if (reconnectTimer.current !== null) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "stop" }));
    }
  }, []);

  const isOpen = useCallback(() => {
    return wsRef.current?.readyState === WebSocket.OPEN;
  }, []);

  return { send, stop, isOpen };
}
