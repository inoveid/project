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

function makeHandoffItem(
  itemType: HandoffItem["itemType"],
  fromAgent: string,
  toAgent: string,
  content: string,
): HandoffItem {
  return {
    id: crypto.randomUUID(),
    itemType,
    agentName: toAgent,
    fromAgent,
    toAgent,
    content,
    created_at: new Date().toISOString(),
  };
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
      setItems((prev) => prev.filter((i) => !isHandoffItem(i) || i.id !== "__activity__"));
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

    case "tool_use": {
      setStatus("tool");
      const toolLabels: Record<string, string> = {
        Read: "Читает файл...",
        Edit: "Редактирует файл...",
        Write: "Пишет файл...",
        Bash: "Выполняет команду...",
        Grep: "Ищет в файлах...",
        Glob: "Ищет файлы...",
        Agent: "Запускает подзадачу...",
      };
      const toolLabel = toolLabels[event.tool_name] || `${event.tool_name}...`;
      refs.toolsRef.current.push({
        tool_name: event.tool_name,
        tool_input: event.tool_input,
      });
      // Update streaming message with tool info
      setItems((prev) => {
        const idx = prev.findIndex((i) => !isHandoffItem(i) && i.id === "__streaming__");
        if (idx === -1) return prev;
        const current = prev[idx] as Message;
        const updated: Message = {
          ...current,
          content: refs.textRef.current,
          tool_uses: refs.toolsRef.current.map((t) => ({ ...t })),
        };
        const result = [...prev];
        result[idx] = updated;
        return result;
      });
      setItems((prev) => {
        const withoutActivity = prev.filter((i) => !isHandoffItem(i) || i.id !== "__activity__");
        const activityItem: HandoffItem = {
          id: "__activity__",
          itemType: "activity",
          agentName: "system",
          content: toolLabel,
          created_at: new Date().toISOString(),
        };
        return [...withoutActivity, activityItem];
      });
      break;
    }

    case "tool_result": {
      const lastTool = refs.toolsRef.current[refs.toolsRef.current.length - 1];
      if (lastTool) {
        lastTool.result = event.content;
      }
      setItems((prev) => {
        const idx = prev.findIndex((i) => !isHandoffItem(i) && i.id === "__streaming__");
        if (idx === -1) return prev;
        const current = prev[idx] as Message;
        const updated: Message = {
          ...current,
          content: refs.textRef.current,
          tool_uses: refs.toolsRef.current.map((t) => ({ ...t })),
        };
        const result = [...prev];
        result[idx] = updated;
        return result;
      });
      setItems((prev) => {
        const withoutActivity = prev.filter((i) => !isHandoffItem(i) || i.id !== "__activity__");
        const activityItem: HandoffItem = {
          id: "__activity__",
          itemType: "activity",
          agentName: "system",
          content: "Думает...",
          created_at: new Date().toISOString(),
        };
        return [...withoutActivity, activityItem];
      });
      break;
    }

    case "done": {
      setItems((prev) => prev.filter((i) => !isHandoffItem(i) || i.id !== "__activity__"));
      const text = refs.textRef.current;
      const tools = [...refs.toolsRef.current];
      refs.textRef.current = "";
      refs.toolsRef.current = [];

      setItems((prev) => {
        const withoutStreaming = prev.filter(
          (i) => !(!isHandoffItem(i) && i.id === "__streaming__"),
        );
        if (!text && tools.length === 0) return withoutStreaming;

        const msg = makeLocalMessage("assistant", text);
        msg.tool_uses = tools.length > 0 ? tools : null;
        const streamingIdx = prev.findIndex(
          (i) => !isHandoffItem(i) && i.id === "__streaming__",
        );
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
        chain: event.chain,
        steps: event.steps,
        workflowAgents: event.workflow_agents,
      });
      setStatus("awaiting_approval");
      setItems((prev) => [
        ...prev,
        makeHandoffItem("approval_required", event.from_agent, event.to_agent, event.task),
      ]);
      break;
    }

    case "handoff_start": {
      setItems((prev) => [
        ...prev,
        makeHandoffItem("handoff_start", event.from_agent, event.to_agent, event.task),
      ]);
      break;
    }

    case "status": {
      const statusLabels: Record<string, string> = {
        thinking: "Думает...",
      };
      const label = statusLabels[event.status] || event.status;
      setItems((prev) => {
        const withoutActivity = prev.filter((i) => !isHandoffItem(i) || i.id !== "__activity__");
        const activityItem: HandoffItem = {
          id: "__activity__",
          itemType: "activity",
          agentName: "system",
          content: label,
          created_at: new Date().toISOString(),
        };
        return [...withoutActivity, activityItem];
      });
      setStatus("typing");
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

    default:
      console.warn("[chat] Unknown WS event type:", (event as Record<string, unknown>).type);
      break;
  }
}
