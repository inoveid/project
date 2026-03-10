import { useEffect, useState } from "react";
import { useToast, type Toast } from "../../hooks/useToast";

const TYPE_STYLES: Record<Toast["type"], { bg: string; border: string; icon: string }> = {
  info: { bg: "bg-blue-50", border: "border-blue-200", icon: "ℹ" },
  success: { bg: "bg-green-50", border: "border-green-200", icon: "✓" },
  warning: { bg: "bg-yellow-50", border: "border-yellow-200", icon: "⚠" },
  error: { bg: "bg-red-50", border: "border-red-200", icon: "✕" },
};

const ICON_COLORS: Record<Toast["type"], string> = {
  info: "text-blue-600",
  success: "text-green-600",
  warning: "text-yellow-600",
  error: "text-red-600",
};

function ToastItem({ toast, onClose }: { toast: Toast; onClose: () => void }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const frame = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  const style = TYPE_STYLES[toast.type];
  const iconColor = ICON_COLORS[toast.type];

  const handleClose = () => {
    setVisible(false);
    setTimeout(onClose, 200);
  };

  return (
    <div
      role="alert"
      className={[
        "pointer-events-auto w-80 rounded-lg border shadow-lg p-3 transition-all duration-200",
        style.bg,
        style.border,
        visible ? "translate-x-0 opacity-100" : "translate-x-4 opacity-0",
      ].join(" ")}
    >
      <div className="flex items-start gap-2">
        <span className={`text-sm font-bold mt-0.5 ${iconColor}`}>
          {style.icon}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-900">{toast.title}</p>
          <p className="text-xs text-gray-600 mt-0.5 break-words">{toast.message}</p>
          {toast.action && (
            <button
              className="text-xs font-medium text-blue-600 hover:text-blue-800 mt-1"
              onClick={() => {
                toast.action?.onClick();
                handleClose();
              }}
            >
              {toast.action.label}
            </button>
          )}
        </div>
        <button
          className="text-gray-400 hover:text-gray-600 text-sm leading-none"
          onClick={handleClose}
          aria-label="Close notification"
        >
          ×
        </button>
      </div>
    </div>
  );
}

export function ToastContainer() {
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none"
    >
      {toasts.map((toast) => (
        <ToastItem
          key={toast.id}
          toast={toast}
          onClose={() => removeToast(toast.id)}
        />
      ))}
    </div>
  );
}
