import { useCallback, useEffect, useRef, useState } from "react";
import type { Message, ToolUse, WsIncoming } from "../types";

export type ChatStatus = "idle" | "connecting" | "connected" | "typing" | "tool" | "disconnected";

interface UseChatResult {
  messages: Message[];
  status: ChatStatus;
  error: string | null;
  sendMessage: (content: string) => void;
  stopAgent: () => void;
}

function makeLocalMessage(role: "user" | "assistant", content: string): Message {
  return {
    id: crypto.randomUUID(),
    session_id: "",
    role,
    content,
    tool_uses: null,
    created_at: new Date().toISOString(),
  };
}

const RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECT_ATTEMPTS = 5;

export function useChat(
  sessionId: string,
  initialMessages: Message[],
  enabled: boolean,
): UseChatResult {
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<ChatStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingTextRef = useRef("");
  const pendingToolsRef = useRef<ToolUse[]>([]);
  const initializedRef = useRef(false);
  const stoppedRef = useRef(false);
  const initialMessagesRef = useRef(initialMessages);
  initialMessagesRef.current = initialMessages;

  const handleEvent = useCallback(
    (event: WsIncoming) => {
      switch (event.type) {
        case "assistant_text":
          setStatus("typing");
          pendingTextRef.current += event.content;
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.role === "assistant" && last.id === "__streaming__") {
              return [
                ...prev.slice(0, -1),
                { ...last, content: pendingTextRef.current },
              ];
            }
            const streaming = makeLocalMessage("assistant", pendingTextRef.current);
            streaming.id = "__streaming__";
            return [...prev, streaming];
          });
          break;

        case "tool_use":
          setStatus("tool");
          pendingToolsRef.current.push({
            tool_name: event.tool_name,
            tool_input: event.tool_input,
          });
          break;

        case "tool_result": {
          const lastTool = pendingToolsRef.current[pendingToolsRef.current.length - 1];
          if (lastTool) {
            lastTool.result = event.content;
          }
          break;
        }

        case "done": {
          const text = pendingTextRef.current;
          const tools = [...pendingToolsRef.current];
          pendingTextRef.current = "";
          pendingToolsRef.current = [];

          setMessages((prev) => {
            const withoutStreaming = prev.filter((m) => m.id !== "__streaming__");
            if (!text && tools.length === 0) return withoutStreaming;

            const msg = makeLocalMessage("assistant", text);
            msg.tool_uses = tools.length > 0 ? tools : null;
            return [...withoutStreaming, msg];
          });
          setStatus("connected");
          break;
        }

        case "error":
          setError(event.error);
          setStatus("connected");
          break;
      }
    },
    [],
  );

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
        handleEvent(data);
      } catch {
        setError("Failed to parse server message");
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      setStatus("disconnected");
      if (!stoppedRef.current && reconnectCount.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectCount.current += 1;
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
      }
    };

    ws.onerror = () => {
      setError("WebSocket connection error");
    };
  }, [sessionId, handleEvent]);

  // Set initial messages when session loads or API data refreshes
  useEffect(() => {
    if (!enabled) return;
    if (initializedRef.current && initialMessagesRef.current.length === 0) return;
    initializedRef.current = true;
    setMessages(initialMessagesRef.current);
  }, [enabled, initialMessages.length]);

  // Connect/disconnect WS
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
  }, [enabled, connect]);

  const sendMessage = useCallback(
    (content: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      setMessages((prev) => [...prev, makeLocalMessage("user", content)]);
      wsRef.current.send(JSON.stringify({ type: "message", content }));
      setStatus("typing");
    },
    [],
  );

  const stopAgent = useCallback(() => {
    stoppedRef.current = true;
    if (reconnectTimer.current !== null) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: "stop" }));
  }, []);

  return { messages, status, error, sendMessage, stopAgent };
}
