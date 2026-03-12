import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ApprovalRequest, ChatItem, HandoffItem, Message, ToolUse, WsIncoming } from "../../types";
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

  const refs: PendingRefs = useMemo(() => ({
    textRef: pendingTextRef,
    toolsRef: pendingToolsRef,
    subAgentRef: pendingSubAgentRef,
  }), []);

  const onEvent = useCallback(
    (event: WsIncoming) => {
      handleEvent(event, refs, { setItems, setStatus, setError, setPendingApproval });
    },
    [refs, setItems, setStatus, setError, setPendingApproval],
  );

  const onDisconnect = useCallback(() => {
    pendingTextRef.current = "";
    pendingToolsRef.current = [];
    pendingSubAgentRef.current = null;
    setItems((prev) => prev.filter((i) => {
      if (isHandoffItem(i)) return i.id !== "__sub_agent_streaming__";
      return i.id !== "__streaming__";
    }));
  }, []);

  // Set initial messages when session loads or API data refreshes.
  // IMPORTANT: must be declared before useChatSocket to preserve effect ordering.
  useEffect(() => {
    if (!enabled) return;
    if (initializedRef.current && initialMessagesRef.current.length === 0) return;
    initializedRef.current = true;
    setItems(initialMessagesRef.current);
  }, [enabled, initialMessages.length]);

  const { send, stop, isOpen } = useChatSocket({
    sessionId,
    enabled,
    initializedRef,
    onEvent,
    onDisconnect,
    setStatus,
    setError,
  });

  const sendMessage = useCallback(
    (content: string) => {
      if (!isOpen()) {
        setError("Connection not ready. Please wait and try again.");
        return;
      }
      setError(null);
      setItems((prev) => [...prev, makeLocalMessage("user", content)]);
      send(JSON.stringify({ type: "message", content }));
      setStatus("typing");
    },
    [send, isOpen],
  );

  const stopAgent = useCallback(() => {
    stop();
  }, [stop]);

  const approveHandoff = useCallback(() => {
    if (!isOpen()) return;
    setPendingApproval(null);
    setStatus("typing");
    send(JSON.stringify({ type: "approve" }));
  }, [send, isOpen]);

  const rejectHandoff = useCallback(() => {
    if (!isOpen()) return;
    setPendingApproval(null);
    setStatus("connected");
    send(JSON.stringify({ type: "reject" }));
  }, [send, isOpen]);

  // Auto-send first pending message when WebSocket connects
  // (e.g. starting_prompt created by task start)
  const autoSentRef = useRef(false);
  useEffect(() => {
    if (status !== "connected" || autoSentRef.current) return;
    const msgs = initialMessagesRef.current;
    if (msgs.length === 0) return;
    const lastMsg = msgs[msgs.length - 1];
    if (lastMsg.role === "user") {
      autoSentRef.current = true;
      send(JSON.stringify({ type: "message", content: lastMsg.content }));
      setStatus("typing");
    }
  }, [status, send]);

  const messages = items.filter((i): i is Message => !isHandoffItem(i));

  return { items, messages, status, error, pendingApproval, sendMessage, stopAgent, approveHandoff, rejectHandoff };
}
