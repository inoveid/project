import { useCallback, useEffect, useRef, useState } from "react";
import type { ApprovalRequest, ChatItem, HandoffItem, Message, ToolUse, WsIncoming } from "../types";
import { isHandoffItem } from "../types";

export type ChatStatus = "idle" | "connecting" | "connected" | "typing" | "tool" | "disconnected" | "awaiting_approval";

interface UseChatResult {
  items: ChatItem[];
  messages: Message[];
  status: ChatStatus;
  error: string | null;
  pendingApproval: ApprovalRequest | null;
  sendMessage: (content: string) => void;
  stopAgent: () => void;
  approveHandoff: () => void;
  rejectHandoff: () => void;
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
  const [items, setItems] = useState<ChatItem[]>([]);
  const [status, setStatus] = useState<ChatStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [pendingApproval, setPendingApproval] = useState<ApprovalRequest | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingTextRef = useRef("");
  const pendingToolsRef = useRef<ToolUse[]>([]);
  const pendingSubAgentRef = useRef<HandoffItem | null>(null);
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
          setItems((prev) => {
            const last = prev[prev.length - 1];
            if (last && !isHandoffItem(last) && last.role === "assistant" && last.id === "__streaming__") {
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

          setItems((prev) => {
            const withoutStreaming = prev.filter(
              (i) => !(!isHandoffItem(i) && i.id === "__streaming__"),
            );
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

        case "approval_required": {
          // HITL gate: граф паузирован, ждём решения пользователя
          setPendingApproval({
            fromAgent: event.from_agent,
            toAgent: event.to_agent,
            task: event.task,
          });
          setStatus("awaiting_approval");
          // Добавить визуальный маркер в чат
          const item: HandoffItem = {
            id: crypto.randomUUID(),
            itemType: "approval_required",
            agentName: event.to_agent,
            fromAgent: event.from_agent,
            toAgent: event.to_agent,
            content: event.task,
            created_at: new Date().toISOString(),
          };
          setItems((prev) => [...prev, item]);
          break;
        }

        case "handoff_start": {
          const item: HandoffItem = {
            id: crypto.randomUUID(),
            itemType: "handoff_start",
            agentName: event.to_agent,
            fromAgent: event.from_agent,
            toAgent: event.to_agent,
            content: event.task,
            created_at: new Date().toISOString(),
          };
          setItems((prev) => [...prev, item]);
          break;
        }

        case "sub_agent_assistant_text": {
          if (!pendingSubAgentRef.current) {
            pendingSubAgentRef.current = {
              id: "__sub_agent_streaming__",
              itemType: "sub_agent_turn",
              agentName: event.agent_name,
              content: "",
              toolUses: [],
              created_at: new Date().toISOString(),
            };
          }
          pendingSubAgentRef.current.content += event.content;
          const snapshot = { ...pendingSubAgentRef.current };
          setItems((prev) => {
            const withoutPending = prev.filter((i) => i.id !== "__sub_agent_streaming__");
            return [...withoutPending, snapshot];
          });
          break;
        }

        case "sub_agent_tool_use": {
          if (pendingSubAgentRef.current) {
            pendingSubAgentRef.current.toolUses = [
              ...(pendingSubAgentRef.current.toolUses ?? []),
              { tool_name: event.tool_name, tool_input: event.tool_input },
            ];
          }
          break;
        }

        case "sub_agent_tool_result": {
          if (pendingSubAgentRef.current) {
            const tools = pendingSubAgentRef.current.toolUses ?? [];
            const last = tools[tools.length - 1];
            if (last) last.result = event.content;
          }
          break;
        }

        case "sub_agent_error":
          setError(`[${event.agent_name}] ${event.error}`);
          break;

        case "handoff_done": {
          if (pendingSubAgentRef.current) {
            const final: HandoffItem = {
              ...pendingSubAgentRef.current,
              id: crypto.randomUUID(),
              itemType: "handoff_done",
            };
            pendingSubAgentRef.current = null;
            setItems((prev) => {
              const withoutPending = prev.filter((i) => i.id !== "__sub_agent_streaming__");
              return [...withoutPending, final];
            });
          }
          break;
        }

        case "handoff_cycle_detected": {
          const item: HandoffItem = {
            id: crypto.randomUUID(),
            itemType: "handoff_cycle",
            agentName: "system",
            content: event.message,
            created_at: new Date().toISOString(),
          };
          setItems((prev) => [...prev, item]);
          break;
        }
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
    setItems(initialMessagesRef.current);
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
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        setError("Connection not ready. Please wait and try again.");
        return;
      }
      setError(null);
      setItems((prev) => [...prev, makeLocalMessage("user", content)]);
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

  const approveHandoff = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setPendingApproval(null);
    setStatus("typing");
    wsRef.current.send(JSON.stringify({ type: "approve" }));
  }, []);

  const rejectHandoff = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setPendingApproval(null);
    setStatus("connected");
    wsRef.current.send(JSON.stringify({ type: "reject" }));
  }, []);

  const messages = items.filter((i): i is Message => !isHandoffItem(i));

  return { items, messages, status, error, pendingApproval, sendMessage, stopAgent, approveHandoff, rejectHandoff };
}
