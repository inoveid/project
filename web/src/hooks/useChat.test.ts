import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { useChat } from "./useChat";
import type { Message } from "../types";
import { isHandoffItem } from "../types";

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

  it("does not reconnect after stopAgent", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() => result.current.stopAgent());
    act(() => ws.simulateClose());

    act(() => vi.advanceTimersByTime(2000));
    // Should NOT have created a new WS instance
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it("handoff_start adds HandoffItem to items", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() =>
      ws.simulateMessage({
        type: "handoff_start",
        from_agent: "orchestrator",
        to_agent: "coder",
        task: "Write tests",
      }),
    );

    expect(result.current.items).toHaveLength(1);
    const item = result.current.items[0]!;
    expect(isHandoffItem(item)).toBe(true);
    if (isHandoffItem(item)) {
      expect(item.itemType).toBe("handoff_start");
      expect(item.agentName).toBe("coder");
      expect(item.fromAgent).toBe("orchestrator");
      expect(item.toAgent).toBe("coder");
      expect(item.content).toBe("Write tests");
    }
    // messages should not include handoff items
    expect(result.current.messages).toHaveLength(0);
  });

  it("sub_agent_assistant_text accumulates content", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() =>
      ws.simulateMessage({
        type: "sub_agent_assistant_text",
        agent_name: "coder",
        content: "Hello ",
      }),
    );
    expect(result.current.items).toHaveLength(1);
    const item1 = result.current.items[0]!;
    expect(isHandoffItem(item1)).toBe(true);
    if (isHandoffItem(item1)) {
      expect(item1.content).toBe("Hello ");
      expect(item1.itemType).toBe("sub_agent_turn");
    }

    act(() =>
      ws.simulateMessage({
        type: "sub_agent_assistant_text",
        agent_name: "coder",
        content: "world",
      }),
    );
    expect(result.current.items).toHaveLength(1);
    const item2 = result.current.items[0]!;
    if (isHandoffItem(item2)) {
      expect(item2.content).toBe("Hello world");
    }
  });

  it("handoff_done finalizes sub_agent_turn item", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() =>
      ws.simulateMessage({
        type: "sub_agent_assistant_text",
        agent_name: "coder",
        content: "Done!",
      }),
    );
    act(() =>
      ws.simulateMessage({
        type: "handoff_done",
        agent_name: "coder",
      }),
    );

    expect(result.current.items).toHaveLength(1);
    const item = result.current.items[0]!;
    expect(isHandoffItem(item)).toBe(true);
    if (isHandoffItem(item)) {
      expect(item.itemType).toBe("handoff_done");
      expect(item.content).toBe("Done!");
      expect(item.id).not.toBe("__sub_agent_streaming__");
    }
  });

  it("messages filters only Message items", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    // Add a handoff item
    act(() =>
      ws.simulateMessage({
        type: "handoff_start",
        from_agent: "orchestrator",
        to_agent: "coder",
        task: "Do work",
      }),
    );

    // Add a regular message
    act(() => ws.simulateMessage({ type: "assistant_text", content: "Hi" }));
    act(() => ws.simulateMessage({ type: "done" }));

    // items should have both
    expect(result.current.items).toHaveLength(2);
    // messages should only have the Message
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]?.content).toBe("Hi");
  });

  it("handoff_cycle_detected adds cycle item", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() =>
      ws.simulateMessage({
        type: "handoff_cycle_detected",
        message: "Cycle detected: A -> B -> A",
      }),
    );

    expect(result.current.items).toHaveLength(1);
    const item = result.current.items[0]!;
    expect(isHandoffItem(item)).toBe(true);
    if (isHandoffItem(item)) {
      expect(item.itemType).toBe("handoff_cycle");
      expect(item.content).toBe("Cycle detected: A -> B -> A");
    }
  });

  it("resets pending refs and removes __streaming__ on WS disconnect", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() => ws.simulateMessage({ type: "assistant_text", content: "Hello" }));
    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0]!).toHaveProperty("id", "__streaming__");

    act(() => ws.simulateClose());

    expect(result.current.items).toHaveLength(0);
    expect(result.current.status).toBe("disconnected");
  });

  it("does not carry stale text after reconnect", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws1 = MockWebSocket.instances[0]!;
    act(() => ws1.simulateOpen());

    act(() => ws1.simulateMessage({ type: "assistant_text", content: "Old " }));
    act(() => ws1.simulateClose());

    act(() => vi.advanceTimersByTime(2000));
    const ws2 = MockWebSocket.instances[1]!;
    act(() => ws2.simulateOpen());

    act(() => ws2.simulateMessage({ type: "assistant_text", content: "New" }));
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]?.content).toBe("New");
  });

  it("tool_use triggers re-render with streaming item", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() => ws.simulateMessage({ type: "assistant_text", content: "Hi" }));
    act(() =>
      ws.simulateMessage({
        type: "tool_use",
        tool_name: "Read",
        tool_input: { path: "/a.ts" },
      }),
    );

    expect(result.current.messages).toHaveLength(1);
    const msg = result.current.messages[0]!;
    expect(msg.id).toBe("__streaming__");
    expect(msg.tool_uses).toEqual([
      { tool_name: "Read", tool_input: { path: "/a.ts" } },
    ]);
  });

  it("tool_result triggers re-render updating streaming item", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() => ws.simulateMessage({ type: "assistant_text", content: "Hi" }));
    act(() =>
      ws.simulateMessage({
        type: "tool_use",
        tool_name: "Read",
        tool_input: { path: "/a.ts" },
      }),
    );
    act(() =>
      ws.simulateMessage({
        type: "tool_result",
        content: "file contents",
      }),
    );

    const msg = result.current.messages[0]!;
    expect(msg.tool_uses?.[0]?.result).toBe("file contents");
  });

  it("sub_agent_tool_use triggers re-render", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() =>
      ws.simulateMessage({
        type: "sub_agent_assistant_text",
        agent_name: "coder",
        content: "Working",
      }),
    );
    act(() =>
      ws.simulateMessage({
        type: "sub_agent_tool_use",
        tool_name: "Write",
        tool_input: { path: "/b.ts" },
      }),
    );

    expect(result.current.items).toHaveLength(1);
    const item = result.current.items[0]!;
    expect(isHandoffItem(item)).toBe(true);
    if (isHandoffItem(item)) {
      expect(item.toolUses).toHaveLength(1);
      expect(item.toolUses?.[0]?.tool_name).toBe("Write");
    }
  });

  it("sub_agent_tool_result triggers re-render", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() =>
      ws.simulateMessage({
        type: "sub_agent_assistant_text",
        agent_name: "coder",
        content: "Working",
      }),
    );
    act(() =>
      ws.simulateMessage({
        type: "sub_agent_tool_use",
        tool_name: "Write",
        tool_input: { path: "/b.ts" },
      }),
    );
    act(() =>
      ws.simulateMessage({
        type: "sub_agent_tool_result",
        content: "ok",
      }),
    );

    const item = result.current.items[0]!;
    if (isHandoffItem(item)) {
      expect(item.toolUses?.[0]?.result).toBe("ok");
    }
  });

  it("approval_required sets pendingApproval state", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() =>
      ws.simulateMessage({
        type: "approval_required",
        from_agent: "orchestrator",
        to_agent: "coder",
        task: "Write the feature",
      }),
    );

    expect(result.current.pendingApproval).not.toBeNull();
    expect(result.current.status).toBe("awaiting_approval");
  });

  it("approval_required shows agent info in pendingApproval", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() =>
      ws.simulateMessage({
        type: "approval_required",
        from_agent: "orchestrator",
        to_agent: "coder",
        task: "Write the feature",
      }),
    );

    expect(result.current.pendingApproval?.fromAgent).toBe("orchestrator");
    expect(result.current.pendingApproval?.toAgent).toBe("coder");
    expect(result.current.pendingApproval?.task).toBe("Write the feature");
  });

  it("approveHandoff sends approve message via WebSocket", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() =>
      ws.simulateMessage({
        type: "approval_required",
        from_agent: "orchestrator",
        to_agent: "coder",
        task: "Write the feature",
      }),
    );
    act(() => result.current.approveHandoff());

    expect(ws.sent).toHaveLength(1);
    expect(JSON.parse(ws.sent[0]!)).toEqual({ type: "approve" });
    expect(result.current.pendingApproval).toBeNull();
    expect(result.current.status).toBe("typing");
  });

  it("rejectHandoff sends reject message via WebSocket", () => {
    const { result } = renderHook(() => useChat("s-1", [], true));
    const ws = MockWebSocket.instances[0]!;
    act(() => ws.simulateOpen());

    act(() =>
      ws.simulateMessage({
        type: "approval_required",
        from_agent: "orchestrator",
        to_agent: "coder",
        task: "Write the feature",
      }),
    );
    act(() => result.current.rejectHandoff());

    expect(ws.sent).toHaveLength(1);
    expect(JSON.parse(ws.sent[0]!)).toEqual({ type: "reject" });
    expect(result.current.pendingApproval).toBeNull();
    expect(result.current.status).toBe("connected");
  });
});
