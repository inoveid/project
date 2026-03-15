import { useCallback, useEffect, useRef, useState } from "react";

export type TerminalStatus = "disconnected" | "connecting" | "connected";

interface UseTerminalOptions {
  productId: string;
  enabled: boolean;
  onData: (data: string) => void;
}

export interface UseTerminalResult {
  status: TerminalStatus;
  send: (data: string) => void;
  resize: (cols: number, rows: number) => void;
  reconnect: () => void;
}

const RECONNECT_DELAY = 2000;
const MAX_RECONNECT = 10;

export function useTerminal({ productId, enabled, onData }: UseTerminalOptions): UseTerminalResult {
  const [status, setStatus] = useState<TerminalStatus>("disconnected");
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const onDataRef = useRef(onData);
  onDataRef.current = onData;
  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;

  const connect = useCallback(() => {
    if (!enabledRef.current || !productId) return;
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) return;

    setStatus("connecting");

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${window.location.host}/api/ws/products/${productId}/terminal`;
    const ws = new WebSocket(url);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      // Stale check: this WS may have been replaced during StrictMode remount
      if (wsRef.current !== ws) {
        ws.close();
        return;
      }
      setStatus("connected");
      reconnectCount.current = 0;
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        const text = new TextDecoder().decode(event.data);
        onDataRef.current(text);
      } else if (typeof event.data === "string") {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "error") {
            console.error("[terminal]", msg.error);
          } else if (msg.type === "idle_timeout") {
            console.warn("[terminal] idle timeout");
          }
        } catch {
          onDataRef.current(event.data);
        }
      }
    };

    ws.onclose = () => {
      // Stale check: if wsRef already points to a newer WS, do nothing
      if (wsRef.current !== ws) return;

      setStatus("disconnected");
      wsRef.current = null;

      if (enabledRef.current && reconnectCount.current < MAX_RECONNECT) {
        reconnectCount.current++;
        const delay = RECONNECT_DELAY * Math.min(reconnectCount.current, 5);
        reconnectTimer.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      // onclose will fire after this
    };
  }, [productId]);

  const send = useCallback((data: string) => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(new TextEncoder().encode(data));
    }
  }, []);

  const resize = useCallback((cols: number, rows: number) => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "resize", cols, rows }));
    }
  }, []);

  const reconnect = useCallback(() => {
    reconnectCount.current = 0;
    connect();
  }, [connect]);

  useEffect(() => {
    if (enabled) {
      connect();
    }
    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        // Clear ref BEFORE closing, so onclose handler sees stale WS and skips
        const ws = wsRef.current;
        wsRef.current = null;
        ws.close();
      }
    };
  }, [enabled, connect]);

  return { status, send, resize, reconnect };
}
