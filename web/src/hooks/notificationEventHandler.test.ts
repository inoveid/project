import { describe, expect, it, vi } from "vitest";
import {
  handleNotificationEvent,
  isNotificationEvent,
  type NotificationEvent,
} from "./notificationEventHandler";

describe("isNotificationEvent", () => {
  it("returns true for known event types", () => {
    expect(isNotificationEvent({ type: "approval_required" })).toBe(true);
    expect(isNotificationEvent({ type: "max_cycles_reached" })).toBe(true);
    expect(isNotificationEvent({ type: "task_completed" })).toBe(true);
    expect(isNotificationEvent({ type: "task_error" })).toBe(true);
  });

  it("returns false for unknown types", () => {
    expect(isNotificationEvent({ type: "unknown" })).toBe(false);
    expect(isNotificationEvent({})).toBe(false);
    expect(isNotificationEvent(null)).toBe(false);
    expect(isNotificationEvent("string")).toBe(false);
    expect(isNotificationEvent({ type: 123 })).toBe(false);
  });
});

describe("handleNotificationEvent", () => {
  function setup() {
    const addToast = vi.fn().mockReturnValue("toast-id");
    const navigateToTask = vi.fn();
    return { addToast, navigateToTask };
  }

  it("maps approval_required to warning toast with duration=0", () => {
    const { addToast, navigateToTask } = setup();
    const event: NotificationEvent = {
      type: "approval_required",
      from_agent: "Coder",
      to_agent: "Reviewer",
      task_id: "task-1",
    };
    handleNotificationEvent(event, { addToast, navigateToTask });

    expect(addToast).toHaveBeenCalledOnce();
    const toast = addToast.mock.calls[0][0];
    expect(toast.type).toBe("warning");
    expect(toast.title).toBe("Ожидает подтверждения");
    expect(toast.message).toBe("Coder → Reviewer");
    expect(toast.duration).toBe(0);
    expect(toast.action).toBeDefined();
    expect(toast.action.label).toBe("Перейти");
  });

  it("maps max_cycles_reached to error toast with duration=0", () => {
    const { addToast, navigateToTask } = setup();
    const event: NotificationEvent = {
      type: "max_cycles_reached",
      agent_name: "Coder",
      reason: "exceeded limit",
    };
    handleNotificationEvent(event, { addToast, navigateToTask });

    const toast = addToast.mock.calls[0][0];
    expect(toast.type).toBe("error");
    expect(toast.title).toBe("Цикл превышен");
    expect(toast.message).toBe("Coder: exceeded limit");
    expect(toast.duration).toBe(0);
  });

  it("maps task_completed to success toast with duration=5000", () => {
    const { addToast, navigateToTask } = setup();
    const event: NotificationEvent = {
      type: "task_completed",
      agent_name: "Coder",
      summary: "All done",
      task_id: "task-2",
    };
    handleNotificationEvent(event, { addToast, navigateToTask });

    const toast = addToast.mock.calls[0][0];
    expect(toast.type).toBe("success");
    expect(toast.duration).toBe(5000);
    expect(toast.message).toBe("Coder: All done");
    expect(toast.action.label).toBe("Открыть");
  });

  it("maps task_error to error toast with duration=0", () => {
    const { addToast, navigateToTask } = setup();
    const event: NotificationEvent = {
      type: "task_error",
      error: "Something broke",
      task_id: "task-3",
    };
    handleNotificationEvent(event, { addToast, navigateToTask });

    const toast = addToast.mock.calls[0][0];
    expect(toast.type).toBe("error");
    expect(toast.message).toBe("Something broke");
    expect(toast.duration).toBe(0);
  });

  it("uses default text when optional fields are missing", () => {
    const { addToast } = setup();
    handleNotificationEvent(
      { type: "approval_required" },
      { addToast },
    );

    const toast = addToast.mock.calls[0][0];
    expect(toast.message).toBe("Agent → Agent");
    expect(toast.action).toBeUndefined();
  });

  it("calls navigateToTask when action button is triggered", () => {
    const { addToast, navigateToTask } = setup();
    handleNotificationEvent(
      { type: "task_completed", task_id: "task-5", agent_name: "Bot" },
      { addToast, navigateToTask },
    );

    const action = addToast.mock.calls[0][0].action;
    action.onClick();
    expect(navigateToTask).toHaveBeenCalledWith("task-5");
  });

  it("omits action when navigateToTask is not provided", () => {
    const { addToast } = setup();
    handleNotificationEvent(
      { type: "task_completed", task_id: "task-6", agent_name: "Bot" },
      { addToast },
    );

    expect(addToast.mock.calls[0][0].action).toBeUndefined();
  });
});
