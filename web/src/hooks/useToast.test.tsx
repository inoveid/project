import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import type { ReactNode } from "react";
import { ToastProvider, useToast } from "./useToast";

function wrapper({ children }: { children: ReactNode }) {
  return <ToastProvider>{children}</ToastProvider>;
}

describe("useToast", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("throws when used outside ToastProvider", () => {
    expect(() => {
      renderHook(() => useToast());
    }).toThrow("useToast must be used within a ToastProvider");
  });

  it("adds and removes a toast", () => {
    const { result } = renderHook(() => useToast(), { wrapper });

    act(() => {
      result.current.addToast({
        type: "info",
        title: "Test",
        message: "Hello",
        duration: 0,
      });
    });

    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0]?.title).toBe("Test");

    act(() => {
      result.current.removeToast(result.current.toasts[0]!.id);
    });

    expect(result.current.toasts).toHaveLength(0);
  });

  it("auto-removes toast after duration", () => {
    const { result } = renderHook(() => useToast(), { wrapper });

    act(() => {
      result.current.addToast({
        type: "success",
        title: "Auto-dismiss",
        message: "Goes away",
        duration: 3000,
      });
    });

    expect(result.current.toasts).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(result.current.toasts).toHaveLength(0);
  });

  it("does not auto-remove toast with duration=0", () => {
    const { result } = renderHook(() => useToast(), { wrapper });

    act(() => {
      result.current.addToast({
        type: "error",
        title: "Persistent",
        message: "Stays forever",
        duration: 0,
      });
    });

    act(() => {
      vi.advanceTimersByTime(60000);
    });

    expect(result.current.toasts).toHaveLength(1);
  });

  it("stacks toasts with newest first", () => {
    const { result } = renderHook(() => useToast(), { wrapper });

    act(() => {
      result.current.addToast({ type: "info", title: "First", message: "1", duration: 0 });
    });

    act(() => {
      result.current.addToast({ type: "info", title: "Second", message: "2", duration: 0 });
    });

    expect(result.current.toasts).toHaveLength(2);
    expect(result.current.toasts[0]?.title).toBe("Second");
    expect(result.current.toasts[1]?.title).toBe("First");
  });

  it("uses default duration of 5000ms when not specified", () => {
    const { result } = renderHook(() => useToast(), { wrapper });

    act(() => {
      result.current.addToast({ type: "info", title: "Default", message: "duration" });
    });

    expect(result.current.toasts).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(4999);
    });
    expect(result.current.toasts).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current.toasts).toHaveLength(0);
  });
});
