import { useCallback, useEffect, useRef, useState } from "react";
import type { ApprovalRequest, ChatItem, HandoffItem, Message, ToolUse } from "../../types";
import { isHandoffItem } from "../../types";
import type { ChatStatus, PendingRefs, UseChatResult } from "./chatState";
import { makeLocalMessage } from "./chatState";
import { handleEvent } from "./chatEventHandler";
import { useChatSocket } from "./useChatSocket";

export function useChat(
  sessionId: string,
  initialMessages: Message[],
  enabled: boolean,
): UseChatResult {
  const [items, setItems] = useState<ChatItem[]>([]);
  const [status, setStatus] = useState<ChatStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [pendingApproval, setPendingApproval] = useState<ApprovalRequest | null>(null);

  const pendingTextRef = useRef("");
  const pendingToolsRef = useRef<ToolUse[]>([]);
  const pendingSubAgentRef = useRef<HandoffItem | null>(null);
  const initializedRef = useRef(false);
  const initialMessagesRef = useRef(initialMessages);
  initialMessagesRef.current = initialMessages;

  const refs: PendingRefs = {
    textRef: pendingTextRef,
    toolsRef: pendingToolsRef,
    subAgentRef: pendingSubAgentRef,
  };

  const onEvent = useCallback(
    (event: Parameters<typeof handleEvent>[0]) => {
      handleEvent(event, refs, { setItems, setStatus, setError, setPendingApproval });
    },
    // refs are stable (useRef objects), setters are stable (useState)
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const resetPendingRefs = useCallback(() => {
    pendingTextRef.current = "";
    pendingToolsRef.current = [];
    pendingSubAgentRef.current = null;
  }, []);

  // Set initial messages when session loads or API data refreshes
  // IMPORTANT: must be declared before useChatSocket to preserve effect ordering
  useEffect(() => {
    if (!enabled) return;
    if (initializedRef.current && initialMessagesRef.current.length === 0) return;
    initializedRef.current = true;
    setItems(initialMessagesRef.current);
  }, [enabled, initialMessages.length]);

  const { wsRef, stoppedRef, reconnectTimer } = useChatSocket({
    sessionId,
    enabled,
    initializedRef,
    onEvent,
    setStatus,
    setError,
    setItems,
    resetPendingRefs,
  });

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
    [wsRef],
  );

  const stopAgent = useCallback(() => {
    stoppedRef.current = true;
    if (reconnectTimer.current !== null) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: "stop" }));
  }, [wsRef, stoppedRef, reconnectTimer]);

  const approveHandoff = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setPendingApproval(null);
    setStatus("typing");
    wsRef.current.send(JSON.stringify({ type: "approve" }));
  }, [wsRef]);

  const rejectHandoff = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setPendingApproval(null);
    setStatus("connected");
    wsRef.current.send(JSON.stringify({ type: "reject" }));
  }, [wsRef]);

  const messages = items.filter((i): i is Message => !isHandoffItem(i));

  return { items, messages, status, error, pendingApproval, sendMessage, stopAgent, approveHandoff, rejectHandoff };
}
