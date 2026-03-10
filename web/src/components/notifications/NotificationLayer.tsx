import { useNotificationSocket } from "../../hooks/useNotificationSocket";
import { ToastContainer } from "./ToastContainer";

/**
 * Global notification layer — connects to WS and renders toast container.
 * Must be rendered inside ToastProvider.
 */
export function NotificationLayer() {
  useNotificationSocket();
  return <ToastContainer />;
}
