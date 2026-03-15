import type { Dispatch, SetStateAction } from "react";
import type { ApprovalRequest, ChatItem, HandoffItem, MRReviewData, Message, WsIncoming } from "../../types";
import { isHandoffItem } from "../../types";
import type { ChatStatus, PendingRefs } from "./chatState";
import { makeLocalMessage } from "./chatState";

export interface EventCallbacks {
  setItems: Dispatch<SetStateAction<ChatItem[]>>;
  setStatus: Dispatch<SetStateAction<ChatStatus>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setPendingApproval: Dispatch<SetStateAction<ApprovalRequest | null>>;
  setMrReview: Dispatch<SetStateAction<MRReviewData | null>>;
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
  const { setItems, setStatus, setError, setPendingApproval, setMrReview } = callbacks;

  console.log("[WS-EVENT]", event.type, event.type === "mr_ready" ? JSON.stringify(event).slice(0, 300) : "");

  switch (event.type) {
    case "assistant_text":
      setStatus("typing");
      refs.textRef.current += event.content;
      setItems((prev) => prev.filter((i) => !isHandoffItem(i) || (i.id !== "__activity__" && i.itemType !== "approval_required" && i.itemType !== "handoff_start") || i.itemType === "activity"));
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

    case "mr_status": {
      const mrItem: HandoffItem = {
        id: `mr-${Date.now()}`,
        itemType: event.status === "merged" ? "mr_merged" : "mr_error",
        agentName: "system",
        content: event.message || (event.status === "merged" ? "MR влит в main" : "Ошибка MR"),
        created_at: new Date().toISOString(),
      };
      setItems((prev) => {
        const withoutActivity = prev.filter((i) => !isHandoffItem(i) || i.id !== "__activity__");
        return [...withoutActivity, mrItem];
      });
      break;
    }

    case "mr_ready": {
      console.log("[MR_READY] task_id:", event.task_id, "diff_files:", event.diff_files?.length, "diff_lines:", event.diff_lines);
      const mrReviewItem: HandoffItem = {
        id: `mr-review-${event.task_id}`,
        itemType: "mr_review",
        agentName: "system",
        content: `Merge Request готов (${event.diff_lines || 0} строк изменений)`,
        created_at: new Date().toISOString(),
        mrData: {
          taskId: event.task_id,
          diffFiles: event.diff_files || [],
          diffLines: event.diff_lines || 0,
        },
      };
      setItems((prev) => {
        // Remove activity items AND approval_required items (MR replaces handoff approval)
        const cleaned = prev.filter((i) => !isHandoffItem(i) || (i.id !== "__activity__" && i.itemType !== "approval_required" && i.itemType !== "handoff_start"));
        return [...cleaned, mrReviewItem];
      });
      setPendingApproval(null);  // Clear any pending handoff approval — MR takes priority
      const mrReviewData = {
        taskId: event.task_id,
        diffFiles: event.diff_files || [],
        diffLines: event.diff_lines || 0,
      };
      console.log("[MR_READY] calling setMrReview with:", JSON.stringify(mrReviewData).slice(0, 200));
      setMrReview(mrReviewData);
      setStatus("awaiting_approval");
      break;
    }

    case "done": {
      console.log("[DONE] received. NOT clearing mrReview.");
      setPendingApproval(null);
      setItems((prev) => prev.filter((i) => !isHandoffItem(i) || (i.id !== "__activity__" && i.itemType !== "approval_required" && i.itemType !== "handoff_start")));
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
      console.log("[APPROVAL_REQUIRED] from:", event.from_agent, "to:", event.to_agent);
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

    case "handoff_completed": {
      setItems((prev) => [
        ...prev,
        makeHandoffItem("handoff_completed", event.from_agent, event.to_agent, event.task),
      ]);
      break;
    }

    case "status": {
      const statusLabels: Record<string, string> = {
        thinking: "Думает...",
      };
      const label = statusLabels[event.status] || event.status;
      // Clear stale approval/MR items when agent starts thinking
      if (event.status === "thinking") {
        console.log("[STATUS] thinking → clearing pendingApproval and mrReview");
        setPendingApproval(null);
        setMrReview(null);
      }
      setItems((prev) => {
        const withoutActivity = prev.filter((i) => !isHandoffItem(i) || (i.id !== "__activity__" && i.itemType !== "approval_required"));
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

    case "sub_agent_spawned": {
      // Persistent item showing sub-agent was spawned
      const spawnItem: HandoffItem = {
        id: `sub-spawn-${event.sub_session_id}`,
        itemType: "activity",
        agentName: event.name,
        content: `→ ${event.name} (${event.role}): ${event.task.slice(0, 150)}`,
        created_at: new Date().toISOString(),
      };
      setItems((prev) => {
        const withoutActivity = prev.filter((i) => !isHandoffItem(i) || i.id !== "__activity__");
        // Also add activity indicator
        const activityItem: HandoffItem = {
          id: "__activity__",
          itemType: "activity",
          agentName: event.name,
          content: `${event.name}: запущен...`,
          created_at: new Date().toISOString(),
        };
        return [...withoutActivity, spawnItem, activityItem];
      });
      break;
    }

    case "sub_agent_assistant_text":
    case "sub_agent_tool_use":
    case "sub_agent_tool_result": {
      const label = event.type === "sub_agent_tool_use"
        ? `${(event as any).sub_agent_name}: ${(event as any).tool_name}...`
        : `${(event as any).sub_agent_name}: работает...`;
      setItems((prev) => {
        const withoutActivity = prev.filter((i) => !isHandoffItem(i) || i.id !== "__activity__");
        const activityItem: HandoffItem = {
          id: "__activity__",
          itemType: "activity",
          agentName: (event as any).sub_agent_name || "sub-agent",
          content: label,
          created_at: new Date().toISOString(),
        };
        return [...withoutActivity, activityItem];
      });
      break;
    }

    case "sub_agent_done": {
      // Update the spawn item to show completion
      setItems((prev) => {
        const withoutActivity = prev.filter((i) => !isHandoffItem(i) || i.id !== "__activity__");
        return withoutActivity.map((item) => {
          if (isHandoffItem(item) && item.id === `sub-spawn-${event.sub_session_id}`) {
            return {
              ...item,
              content: `✓ ${event.name} (${event.role}): завершён${event.output_preview ? " — " + event.output_preview.slice(0, 100) : ""}`,
            };
          }
          return item;
        });
      });
      break;
    }

    case "sub_agent_error": {
      // Update spawn item to show error
      const errSubId = (event as any).sub_session_id;
      setItems((prev) => {
        const withoutActivity = prev.filter((i) => !isHandoffItem(i) || i.id !== "__activity__");
        if (errSubId) {
          return withoutActivity.map((item) => {
            if (isHandoffItem(item) && item.id === `sub-spawn-${errSubId}`) {
              return { ...item, content: `✗ ${event.name || "sub-agent"}: ${(event as any).error || "error"}` };
            }
            return item;
          });
        }
        // Fallback: add error item
        const errorItem: HandoffItem = {
          id: crypto.randomUUID(),
          itemType: "activity",
          agentName: event.name || "sub-agent",
          content: `✗ Sub-agent error: ${(event as any).error || "unknown"}`,
          created_at: new Date().toISOString(),
        };
        return [...withoutActivity, errorItem];
      });
      break;
    }


    case "budget_warning": {
      const warn = event as any;
      const tokens = warn.total_tokens ? `${(warn.total_tokens / 1000).toFixed(1)}k` : "?";
      const msg = `Использовано ${warn.usage_percent ?? 80}% бюджета (${tokens} токенов, $${warn.spent_usd ?? "?"})`;
      setItems((prev) => [...prev, makeLocalMessage("system", msg)]);
      break;
    }

    case "budget_exceeded": {
      const exc = event as any;
      const tokens = exc.total_tokens ? `${(exc.total_tokens / 1000).toFixed(1)}k` : "?";
      const msg = `Лимит исчерпан (${tokens} токенов, $${exc.spent_usd ?? "?"}). Агент остановлен.`;
      setItems((prev) => [...prev, makeLocalMessage("system", msg)]);
      setStatus("connected");
      break;
    }

    default:
      console.warn("[chat] Unknown WS event type:", (event as Record<string, unknown>).type);
      break;
  }
}
