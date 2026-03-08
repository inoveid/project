import type { Dispatch, SetStateAction } from "react";
import type { ApprovalRequest, ChatItem, HandoffItem, Message, WsIncoming } from "../../types";
import { isHandoffItem } from "../../types";
import type { ChatStatus, PendingRefs } from "./chatState";
import { makeLocalMessage } from "./chatState";

export interface EventCallbacks {
  setItems: Dispatch<SetStateAction<ChatItem[]>>;
  setStatus: Dispatch<SetStateAction<ChatStatus>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setPendingApproval: Dispatch<SetStateAction<ApprovalRequest | null>>;
}

function updateStreamingItem(refs: PendingRefs, setItems: Dispatch<SetStateAction<ChatItem[]>>): void {
  setItems((prev) => {
    const idx = prev.findIndex((i) => !isHandoffItem(i) && i.id === "__streaming__");
    if (idx === -1) return prev;
    const current = prev[idx] as Message;
    const updated: Message = {
      ...current,
      content: refs.textRef.current,
      tool_uses: refs.toolsRef.current.length > 0 ? refs.toolsRef.current.map((t) => ({ ...t })) : null,
    };
    const result = [...prev];
    result[idx] = updated;
    return result;
  });
}

function updateSubAgentStreamingItem(refs: PendingRefs, setItems: Dispatch<SetStateAction<ChatItem[]>>): void {
  if (!refs.subAgentRef.current) return;
  const snapshot = { ...refs.subAgentRef.current, toolUses: (refs.subAgentRef.current.toolUses ?? []).map((t) => ({ ...t })) };
  setItems((prev) => {
    const withoutPending = prev.filter((i) => i.id !== "__sub_agent_streaming__");
    return [...withoutPending, snapshot];
  });
}

export function handleEvent(
  event: WsIncoming,
  refs: PendingRefs,
  callbacks: EventCallbacks,
): void {
  const { setItems, setStatus, setError, setPendingApproval } = callbacks;

  switch (event.type) {
    case "assistant_text":
      setStatus("typing");
      refs.textRef.current += event.content;
      setItems((prev) => {
        const last = prev[prev.length - 1];
        if (last && !isHandoffItem(last) && last.role === "assistant" && last.id === "__streaming__") {
          return [
            ...prev.slice(0, -1),
            { ...last, content: refs.textRef.current },
          ];
        }
        const streaming = makeLocalMessage("assistant", refs.textRef.current);
        streaming.id = "__streaming__";
        return [...prev, streaming];
      });
      break;

    case "tool_use":
      setStatus("tool");
      refs.toolsRef.current.push({
        tool_name: event.tool_name,
        tool_input: event.tool_input,
      });
      updateStreamingItem(refs, setItems);
      break;

    case "tool_result": {
      const lastTool = refs.toolsRef.current[refs.toolsRef.current.length - 1];
      if (lastTool) {
        lastTool.result = event.content;
      }
      updateStreamingItem(refs, setItems);
      break;
    }

    case "done": {
      const text = refs.textRef.current;
      const tools = [...refs.toolsRef.current];
      refs.textRef.current = "";
      refs.toolsRef.current = [];

      setItems((prev) => {
        const streamingIdx = prev.findIndex(
          (i) => !isHandoffItem(i) && i.id === "__streaming__",
        );
        const withoutStreaming = prev.filter(
          (i) => !(!isHandoffItem(i) && i.id === "__streaming__"),
        );
        if (!text && tools.length === 0) return withoutStreaming;

        const msg = makeLocalMessage("assistant", text);
        msg.tool_uses = tools.length > 0 ? tools : null;
        if (streamingIdx !== -1) {
          const result = [...withoutStreaming];
          result.splice(streamingIdx, 0, msg);
          return result;
        }
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
      setPendingApproval({
        fromAgent: event.from_agent,
        toAgent: event.to_agent,
        task: event.task,
      });
      setStatus("awaiting_approval");
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
      if (!refs.subAgentRef.current) {
        refs.subAgentRef.current = {
          id: "__sub_agent_streaming__",
          itemType: "sub_agent_turn",
          agentName: event.agent_name,
          content: "",
          toolUses: [],
          created_at: new Date().toISOString(),
        };
      }
      refs.subAgentRef.current.content += event.content;
      const snapshot = { ...refs.subAgentRef.current };
      setItems((prev) => {
        const withoutPending = prev.filter((i) => i.id !== "__sub_agent_streaming__");
        return [...withoutPending, snapshot];
      });
      break;
    }

    case "sub_agent_tool_use": {
      if (refs.subAgentRef.current) {
        refs.subAgentRef.current.toolUses = [
          ...(refs.subAgentRef.current.toolUses ?? []),
          { tool_name: event.tool_name, tool_input: event.tool_input },
        ];
        updateSubAgentStreamingItem(refs, setItems);
      }
      break;
    }

    case "sub_agent_tool_result": {
      if (refs.subAgentRef.current) {
        const tools = refs.subAgentRef.current.toolUses ?? [];
        const last = tools[tools.length - 1];
        if (last) last.result = event.content;
        updateSubAgentStreamingItem(refs, setItems);
      }
      break;
    }

    case "sub_agent_error":
      setError(`[${event.agent_name}] ${event.error}`);
      break;

    case "handoff_done": {
      if (refs.subAgentRef.current) {
        const final: HandoffItem = {
          ...refs.subAgentRef.current,
          id: crypto.randomUUID(),
          itemType: "handoff_done",
        };
        refs.subAgentRef.current = null;
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
}
