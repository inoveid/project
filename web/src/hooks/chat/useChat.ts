import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ApprovalRequest, ChatItem, Message, ToolUse, WsIncoming } from "../../types";
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
  const initializedRef = useRef(false);
  const initialMessagesRef = useRef(initialMessages);
  initialMessagesRef.current = initialMessages;

  const refs: PendingRefs = useMemo(() => ({
    textRef: pendingTextRef,
    toolsRef: pendingToolsRef,
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
    setItems((prev) => prev.filter((i) => {
      if (isHandoffItem(i)) return i.id !== "__activity__";
      return i.id !== "__streaming__";
    }));
  }, []);

  // Set initial messages — MUST be before useChatSocket for effect ordering
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
    setItems((prev) => prev.filter((i) => !isHandoffItem(i) || i.itemType !== "approval_required"));
    setStatus("typing");
    send(JSON.stringify({ type: "approve" }));
  }, [send, isOpen]);

  const refineHandoff = useCallback((comment: string) => {
    if (!isOpen() || !comment.trim()) return;
    setPendingApproval(null);
    setItems((prev) => {
      const filtered = prev.filter((i) => !isHandoffItem(i) || i.itemType !== "approval_required");
      return [...filtered, makeLocalMessage("user", comment)];
    });
    setStatus("typing");
    send(JSON.stringify({ type: "refine", comment }));
  }, [send, isOpen]);

  // Note: initial command is sent by backend (update_task_status / _handle_peer_handoff)
  // via publish_command. No auto-send needed — it caused duplicate messages on reconnect.
  const messages = items.filter((i): i is Message => !isHandoffItem(i));

  return { items, messages, status, error, pendingApproval, sendMessage, stopAgent, approveHandoff, refineHandoff };
}
