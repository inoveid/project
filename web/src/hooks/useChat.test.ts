import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { useChat } from "./useChat";
import type { Message } from "../types";

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];

  constructor() {
    MockWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = 3;
  }

  simulateOpen() {
    this.readyState = 1;
    this.onopen?.();
  }

  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  simulateClose() {
    this.readyState = 3;
    this.onclose?.();
  }
}

const initialMessages: Message[] = [
  {
    id: "msg-1",
    session_id: "s-1",
    role: "user",
    content: "Hello",
    tool_uses: null,
    created_at: "2024-01-01T00:00:00Z",
  },
];

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal("WebSocket", MockWebSocket);
  vi.stubGlobal("crypto", { randomUUID: () => `uuid-${Math.random()}` });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("useChat", () => {
  it("stays idle when not enabled", () => {
    const { result } = renderHook(() => useChat("s-1", [], false));
    expect(result.current.status).toBe("idle");
    expect(MockWebSocket.instances).toHaveLength(0);
  });

  it("connects WebSocket when enabled", () => {
    const { result } = renderHook(() => useChat("s-1", initialMessages, true));
    expect(MockWebSocket.instances).toHaveLength(1);
    expect(result.current.status).toBe("connecting");
    expect(result.current.messages).toEqual(initialMessages);
  });

  it("sets status to connected on WS open", () => {
    const { result } = renderHook(() => useChat("s-1", initialMessages, true));
    act(() => {
      MockWebSocket.instances[0]?.simulateOpen();
    });
    expect(result.current.status).toBe("connected");
  });

  it("buffers streaming assistant_text into one message", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() => ws.simulateMessage({ type: "assistant_text", content: "Hello " }));
    expect(result.current.status).toBe("typing");
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]?.content).toBe("Hello ");

    act(() => ws.simulateMessage({ type: "assistant_text", content: "world" }));
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]?.content).toBe("Hello world");
  });

  it("finalizes message on done event", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() => ws.simulateMessage({ type: "assistant_text", content: "Hi" }));
    act(() => ws.simulateMessage({ type: "done" }));

    expect(result.current.status).toBe("connected");
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]?.id).not.toBe("__streaming__");
    expect(result.current.messages[0]?.content).toBe("Hi");
  });

  it("collects tool_use events", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() =>
      ws.simulateMessage({
        type: "tool_use",
        tool_name: "Read",
        tool_input: { path: "/a.ts" },
      }),
    );
    expect(result.current.status).toBe("tool");

    act(() => ws.simulateMessage({ type: "done" }));
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]?.tool_uses).toEqual([
      { tool_name: "Read", tool_input: { path: "/a.ts" } },
    ]);
  });

  it("sends user message via WebSocket", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() => result.current.sendMessage("Test"));
    expect(ws.sent).toHaveLength(1);
    expect(JSON.parse(ws.sent[0]!)).toEqual({ type: "message", content: "Test" });
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]?.role).toBe("user");
  });

  it("sends stop command", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() => result.current.stopAgent());
    expect(ws.sent).toHaveLength(1);
    expect(JSON.parse(ws.sent[0]!)).toEqual({ type: "stop" });
  });

  it("sets error on error event", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() => ws.simulateMessage({ type: "error", error: "Something broke" }));
    expect(result.current.error).toBe("Something broke");
  });

  it("attempts reconnect on close", () => {
    vi.useFakeTimers();
    renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() => ws.simulateClose());
    expect(MockWebSocket.instances).toHaveLength(1);

    act(() => vi.advanceTimersByTime(2000));
    expect(MockWebSocket.instances).toHaveLength(2);
  });

  it("does not connect when enabled transitions from false", () => {
    const { rerender } = renderHook(
      ({ enabled }) => useChat("s-1", initialMessages, enabled),
      { initialProps: { enabled: false } },
    );
    expect(MockWebSocket.instances).toHaveLength(0);

    rerender({ enabled: true });
    expect(MockWebSocket.instances).toHaveLength(1);
  });
});
