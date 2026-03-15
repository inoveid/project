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
    console.log("[useTerminal] connect() called, enabled:", enabledRef.current, "productId:", productId);
    if (!enabledRef.current || !productId) {
      console.log("[useTerminal] connect() aborted: enabled=", enabledRef.current, "productId=", productId);
      return;
    }
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log("[useTerminal] connect() aborted: already open");
      return;
    }

    // Clean up existing
    if (wsRef.current) {
      console.log("[useTerminal] closing existing WS, readyState:", wsRef.current.readyState);
      wsRef.current.close();
      wsRef.current = null;
    }

    setStatus("connecting");

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${window.location.host}/api/ws/products/${productId}/terminal`;
    console.log("[useTerminal] connecting to:", url);
    const ws = new WebSocket(url);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[useTerminal] WS OPEN");
      setStatus("connected");
      reconnectCount.current = 0;
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        const text = new TextDecoder().decode(event.data);
        console.log("[useTerminal] WS binary msg, len:", event.data.byteLength, "text:", JSON.stringify(text.slice(0, 100)));
        onDataRef.current(text);
      } else if (typeof event.data === "string") {
        console.log("[useTerminal] WS text msg:", event.data.slice(0, 200));
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "error") {
            console.error("[useTerminal] server error:", msg.error);
          } else if (msg.type === "idle_timeout") {
            console.warn("[useTerminal] idle timeout");
          }
        } catch {
          onDataRef.current(event.data);
        }
      }
    };

    ws.onclose = (event) => {
      console.log("[useTerminal] WS CLOSE, code:", event.code, "reason:", event.reason, "wasClean:", event.wasClean);
      setStatus("disconnected");
      wsRef.current = null;

      if (enabledRef.current && reconnectCount.current < MAX_RECONNECT) {
        reconnectCount.current++;
        const delay = RECONNECT_DELAY * Math.min(reconnectCount.current, 5);
        console.log("[useTerminal] will reconnect in", delay, "ms, attempt:", reconnectCount.current);
        reconnectTimer.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = (event) => {
      console.error("[useTerminal] WS ERROR:", event);
    };
  }, [productId]);

  const send = useCallback((data: string) => {
    const ws = wsRef.current;
    const state = ws?.readyState;
    console.log("[useTerminal] send() called, data:", JSON.stringify(data), "ws exists:", !!ws, "readyState:", state);
    if (ws?.readyState === WebSocket.OPEN) {
      const encoded = new TextEncoder().encode(data);
      console.log("[useTerminal] sending binary, bytes:", encoded.length);
      ws.send(encoded);
    } else {
      console.warn("[useTerminal] send() SKIPPED — ws not open");
    }
  }, []);

  const resize = useCallback((cols: number, rows: number) => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      console.log("[useTerminal] resize:", cols, "x", rows);
      ws.send(JSON.stringify({ type: "resize", cols, rows }));
    }
  }, []);

  const reconnect = useCallback(() => {
    console.log("[useTerminal] manual reconnect");
    reconnectCount.current = 0;
    connect();
  }, [connect]);

  useEffect(() => {
    console.log("[useTerminal] useEffect, enabled:", enabled);
    if (enabled) {
      connect();
    }
    return () => {
      console.log("[useTerminal] useEffect cleanup");
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [enabled, connect]);

  return { status, send, resize, reconnect };
}
