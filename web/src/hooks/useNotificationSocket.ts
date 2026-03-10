import { useEffect, useRef } from "react";
import { useToast } from "./useToast";

interface NotificationEvent {
  type: string;
  from_agent?: string;
  to_agent?: string;
  agent_name?: string;
  task?: string;
  task_id?: string;
  summary?: string;
  reason?: string;
  error?: string;
}

const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;

/**
 * Connects to /api/ws/notifications and shows toast notifications
 * for global events (approval_required, task_completed, etc.).
 */
export function useNotificationSocket() {
  const { addToast } = useToast();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const addToastRef = useRef(addToast);
  addToastRef.current = addToast;

  useEffect(() => {
    function connect() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/api/ws/notifications`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectCount.current = 0;
      };

      ws.onmessage = (e: MessageEvent) => {
        try {
          const event = JSON.parse(String(e.data)) as NotificationEvent;
          handleNotificationEvent(event, addToastRef.current);
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (reconnectCount.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectCount.current += 1;
          reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };

      ws.onerror = () => {
        // Will trigger onclose → reconnect
      };
    }

    connect();

    return () => {
      reconnectCount.current = MAX_RECONNECT_ATTEMPTS;
      if (reconnectTimer.current !== null) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
      wsRef.current?.close();
    };
  }, []);
}

function handleNotificationEvent(
  event: NotificationEvent,
  addToast: ReturnType<typeof useToast>["addToast"],
) {
  switch (event.type) {
    case "approval_required":
      addToast({
        type: "warning",
        title: "Ожидает подтверждения",
        message: `${event.from_agent ?? "Agent"} → ${event.to_agent ?? "Agent"}`,
        duration: 0,
        action: event.task_id
          ? { label: "Перейти", onClick: () => navigateToTask(event.task_id) }
          : undefined,
      });
      break;

    case "max_cycles_reached":
      addToast({
        type: "error",
        title: "Цикл превышен",
        message: `${event.agent_name ?? "Agent"}: ${event.reason ?? "max cycles reached"}`,
        duration: 0,
        action: event.task_id
          ? { label: "Перейти", onClick: () => navigateToTask(event.task_id) }
          : undefined,
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
        action: event.task_id
          ? { label: "Открыть", onClick: () => navigateToTask(event.task_id) }
          : undefined,
      });
      break;

    case "task_error":
      addToast({
        type: "error",
        title: "Ошибка задачи",
        message: event.error ?? "Unknown error",
        duration: 0,
        action: event.task_id
          ? { label: "Открыть", onClick: () => navigateToTask(event.task_id) }
          : undefined,
      });
      break;
  }
}

function navigateToTask(taskId: string | undefined) {
  if (!taskId) return;
  // Navigate to dashboard where tasks are displayed
  window.location.hash = `task-${taskId}`;
}
