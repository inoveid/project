import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useToast } from "./useToast";
import {
  handleNotificationEvent,
  isNotificationEvent,
} from "./notificationEventHandler";

const BASE_RECONNECT_MS = 1000;
const MAX_RECONNECT_MS = 30000;
const MAX_RECONNECT_ATTEMPTS = 10;

/**
 * Connects to /api/ws/notifications and shows toast notifications
 * for global events (approval_required, task_completed, etc.).
 *
 * Uses exponential backoff for reconnection and React Router for navigation.
 */
export function useNotificationSocket() {
  const { addToast } = useToast();
  const navigate = useNavigate();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const addToastRef = useRef(addToast);
  const navigateRef = useRef(navigate);
  addToastRef.current = addToast;
  navigateRef.current = navigate;

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
          const data: unknown = JSON.parse(String(e.data));
          if (isNotificationEvent(data)) {
            handleNotificationEvent(data, {
              addToast: addToastRef.current,
              navigateToTask: (taskId: string) => navigateRef.current(`/?task=${taskId}`),
            });
          }
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (reconnectCount.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = Math.min(
            BASE_RECONNECT_MS * 2 ** reconnectCount.current,
            MAX_RECONNECT_MS,
          );
          reconnectCount.current += 1;
          reconnectTimer.current = setTimeout(connect, delay);
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
