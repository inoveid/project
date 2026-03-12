import type { ToastInput } from "./useToast";

/**
 * Discriminated union for notification events received via WebSocket.
 * Add new event types here when extending the notification system.
 */
export type NotificationEvent =
  | {
      type: "approval_required";
      from_agent?: string;
      to_agent?: string;
      task_id?: string;
      task?: string;
    }
  | {
      type: "max_cycles_reached";
      agent_name?: string;
      reason?: string;
      task_id?: string;
    }
  | {
      type: "task_completed";
      agent_name?: string;
      summary?: string;
      task_id?: string;
    }
  | {
      type: "task_error";
      error?: string;
      task_id?: string;
    };

const KNOWN_TYPES = new Set([
  "approval_required",
  "max_cycles_reached",
  "task_completed",
  "task_error",
]);

export function isNotificationEvent(data: unknown): data is NotificationEvent {
  return (
    typeof data === "object" &&
    data !== null &&
    "type" in data &&
    typeof (data as Record<string, unknown>).type === "string" &&
    KNOWN_TYPES.has((data as Record<string, unknown>).type as string)
  );
}

interface HandlerOptions {
  addToast: (input: ToastInput) => string;
  navigateToTask?: (taskId: string) => void;
}

/**
 * Pure function: maps a NotificationEvent to a toast notification.
 * Extracted for easy unit testing and reuse.
 */
export function handleNotificationEvent(
  event: NotificationEvent,
  { addToast, navigateToTask }: HandlerOptions,
): void {
  const makeAction = (label: string, taskId?: string) =>
    taskId && navigateToTask
      ? { label, onClick: () => navigateToTask(taskId) }
      : undefined;

  switch (event.type) {
    case "approval_required":
      addToast({
        type: "warning",
        title: "Ожидает подтверждения",
        message: `${event.from_agent ?? "Agent"} → ${event.to_agent ?? "Agent"}`,
        duration: 7000,
        action: makeAction("Перейти", event.task_id),
      });
      break;

    case "max_cycles_reached":
      addToast({
        type: "error",
        title: "Цикл превышен",
        message: `${event.agent_name ?? "Agent"}: ${event.reason ?? "max cycles reached"}`,
        duration: 7000,
        action: makeAction("Перейти", event.task_id),
      });
      break;

    case "task_completed":
      addToast({
        type: "success",
        title: "Задача выполнена",
        message: event.summary
          ? `${event.agent_name ?? "Agent"}: ${event.summary}`
          : `${event.agent_name ?? "Agent"} завершил задачу`,
        duration: 5000,
        action: makeAction("Открыть", event.task_id),
      });
      break;

    case "task_error":
      addToast({
        type: "error",
        title: "Ошибка задачи",
        message: event.error ?? "Unknown error",
        duration: 7000,
        action: makeAction("Открыть", event.task_id),
      });
      break;
  }
}
