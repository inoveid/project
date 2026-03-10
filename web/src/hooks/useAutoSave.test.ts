import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { useAutoSave } from "./useAutoSave";

describe("useAutoSave", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("calls saveFn after delay", () => {
    const saveFn = vi.fn();
    const { result } = renderHook(() => useAutoSave(saveFn, 500));

    act(() => {
      result.current.schedule();
    });

    expect(saveFn).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(saveFn).toHaveBeenCalledOnce();
  });

  it("debounces multiple schedule calls", () => {
    const saveFn = vi.fn();
    const { result } = renderHook(() => useAutoSave(saveFn, 500));

    act(() => {
      result.current.schedule();
    });

    act(() => {
      vi.advanceTimersByTime(200);
    });

    act(() => {
      result.current.schedule();
    });

    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(saveFn).toHaveBeenCalledOnce();
  });

  it("flush calls saveFn immediately if scheduled", () => {
    const saveFn = vi.fn();
    const { result } = renderHook(() => useAutoSave(saveFn, 500));

    act(() => {
      result.current.schedule();
    });

    act(() => {
      result.current.flush();
    });

    expect(saveFn).toHaveBeenCalledOnce();
  });

  it("flush does nothing if not scheduled", () => {
    const saveFn = vi.fn();
    const { result } = renderHook(() => useAutoSave(saveFn, 500));

    act(() => {
      result.current.flush();
    });

    expect(saveFn).not.toHaveBeenCalled();
  });

  it("cancel stops pending save", () => {
    const saveFn = vi.fn();
    const { result } = renderHook(() => useAutoSave(saveFn, 500));

    act(() => {
      result.current.schedule();
    });

    act(() => {
      result.current.cancel();
    });

    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(saveFn).not.toHaveBeenCalled();
  });
});
