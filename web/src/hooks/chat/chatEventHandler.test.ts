import { describe, expect, it, vi, beforeEach } from "vitest";
import { handleEvent } from "./chatEventHandler";
import type { EventCallbacks } from "./chatEventHandler";
import type { PendingRefs } from "./chatState";
import type { ChatItem, HandoffItem, ToolUse } from "../../types";
import type { ChatStatus } from "./chatState";

function createMockRefs(): PendingRefs {
  return {
    textRef: { current: "" },
    toolsRef: { current: [] as ToolUse[] },
    subAgentRef: { current: null as HandoffItem | null },
  };
}

function createMockCallbacks(): EventCallbacks & {
  getItems: () => ChatItem[];
  getStatus: () => ChatStatus;
  getError: () => string | null;
} {
  let items: ChatItem[] = [];
  let status: ChatStatus = "idle";
  let error: string | null = null;

  return {
    setItems: vi.fn((updater) => {
      items = typeof updater === "function" ? updater(items) : updater;
    }),
    setStatus: vi.fn((updater) => {
      status = typeof updater === "function" ? updater(status) : updater;
    }),
    setError: vi.fn((updater) => {
      error = typeof updater === "function" ? updater(error) : updater;
    }),
    setPendingApproval: vi.fn(),
    getItems: () => items,
    getStatus: () => status,
    getError: () => error,
  };
}

beforeEach(() => {
  vi.stubGlobal("crypto", { randomUUID: () => "test-uuid" });
});

describe("handleEvent", () => {
  describe("assistant_text", () => {
    it("sets status to typing and appends streaming message", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({ type: "assistant_text", content: "Hello" }, refs, cb);

      expect(cb.setStatus).toHaveBeenCalledWith("typing");
      expect(refs.textRef.current).toBe("Hello");
      expect(cb.getItems()).toHaveLength(1);
      expect(cb.getItems()[0]).toHaveProperty("id", "__streaming__");
    });

    it("accumulates text across multiple events", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({ type: "assistant_text", content: "Hello " }, refs, cb);
      handleEvent({ type: "assistant_text", content: "world" }, refs, cb);

      expect(refs.textRef.current).toBe("Hello world");
      expect(cb.getItems()).toHaveLength(1);
      expect(cb.getItems()[0]).toHaveProperty("content", "Hello world");
    });
  });

  describe("tool_use", () => {
    it("sets status to tool and adds tool to refs", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      // Need a streaming item first for updateStreamingItem to work
      handleEvent({ type: "assistant_text", content: "Hi" }, refs, cb);
      handleEvent({ type: "tool_use", tool_name: "Read", tool_input: { path: "/a.ts" } }, refs, cb);

      expect(cb.setStatus).toHaveBeenCalledWith("tool");
      expect(refs.toolsRef.current).toHaveLength(1);
      expect(refs.toolsRef.current[0]).toEqual({ tool_name: "Read", tool_input: { path: "/a.ts" } });
    });
  });

  describe("tool_result", () => {
    it("attaches result to last tool", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({ type: "assistant_text", content: "Hi" }, refs, cb);
      handleEvent({ type: "tool_use", tool_name: "Read", tool_input: { path: "/a.ts" } }, refs, cb);
      handleEvent({ type: "tool_result", content: "file contents" }, refs, cb);

      expect(refs.toolsRef.current[0]?.result).toBe("file contents");
    });
  });

  describe("done", () => {
    it("finalizes streaming message and resets refs", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({ type: "assistant_text", content: "Hi" }, refs, cb);
      handleEvent({ type: "done" }, refs, cb);

      expect(refs.textRef.current).toBe("");
      expect(refs.toolsRef.current).toEqual([]);
      expect(cb.setStatus).toHaveBeenCalledWith("connected");
      const items = cb.getItems();
      expect(items).toHaveLength(1);
      expect(items[0]).not.toHaveProperty("id", "__streaming__");
      expect(items[0]).toHaveProperty("content", "Hi");
    });

    it("removes streaming item when no text and no tools", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({ type: "done" }, refs, cb);

      expect(cb.getItems()).toHaveLength(0);
    });

    it("preserves tool_uses on finalized message", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({ type: "assistant_text", content: "" }, refs, cb);
      handleEvent({ type: "tool_use", tool_name: "Read", tool_input: { path: "/a.ts" } }, refs, cb);
      handleEvent({ type: "done" }, refs, cb);

      const items = cb.getItems();
      expect(items).toHaveLength(1);
      const msg = items[0] as { tool_uses: ToolUse[] | null };
      expect(msg.tool_uses).toEqual([{ tool_name: "Read", tool_input: { path: "/a.ts" } }]);
    });
  });

  describe("error", () => {
    it("sets error and status to connected", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({ type: "error", error: "Something broke" }, refs, cb);

      expect(cb.getError()).toBe("Something broke");
      expect(cb.getStatus()).toBe("connected");
    });
  });

  describe("approval_required", () => {
    it("sets pending approval and adds handoff item", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({
        type: "approval_required",
        from_agent: "orchestrator",
        to_agent: "coder",
        task: "Write code",
      }, refs, cb);

      expect(cb.setPendingApproval).toHaveBeenCalledWith({
        fromAgent: "orchestrator",
        toAgent: "coder",
        task: "Write code",
      });
      expect(cb.setStatus).toHaveBeenCalledWith("awaiting_approval");
      const items = cb.getItems();
      expect(items).toHaveLength(1);
      const item = items[0] as HandoffItem;
      expect(item.itemType).toBe("approval_required");
      expect(item.fromAgent).toBe("orchestrator");
      expect(item.toAgent).toBe("coder");
    });
  });

  describe("handoff_start", () => {
    it("adds handoff_start item", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({
        type: "handoff_start",
        from_agent: "orchestrator",
        to_agent: "coder",
        task: "Do work",
      }, refs, cb);

      const items = cb.getItems();
      expect(items).toHaveLength(1);
      const item = items[0] as HandoffItem;
      expect(item.itemType).toBe("handoff_start");
      expect(item.agentName).toBe("coder");
    });
  });

  describe("sub_agent_assistant_text", () => {
    it("creates sub agent ref and adds streaming item", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({
        type: "sub_agent_assistant_text",
        agent_name: "coder",
        content: "Working",
      }, refs, cb);

      expect(refs.subAgentRef.current).not.toBeNull();
      expect(refs.subAgentRef.current?.content).toBe("Working");
      expect(cb.getItems()).toHaveLength(1);
      const item = cb.getItems()[0] as HandoffItem;
      expect(item.itemType).toBe("sub_agent_turn");
      expect(item.id).toBe("__sub_agent_streaming__");
    });

    it("accumulates content across events", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({ type: "sub_agent_assistant_text", agent_name: "coder", content: "Hello " }, refs, cb);
      handleEvent({ type: "sub_agent_assistant_text", agent_name: "coder", content: "world" }, refs, cb);

      expect(refs.subAgentRef.current?.content).toBe("Hello world");
      expect(cb.getItems()).toHaveLength(1);
    });
  });

  describe("sub_agent_tool_use", () => {
    it("adds tool to sub agent ref", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({ type: "sub_agent_assistant_text", agent_name: "coder", content: "x" }, refs, cb);
      handleEvent({ type: "sub_agent_tool_use", agent_name: "coder", tool_name: "Write", tool_input: { path: "/b.ts" } }, refs, cb);

      expect(refs.subAgentRef.current?.toolUses).toHaveLength(1);
      expect(refs.subAgentRef.current?.toolUses?.[0]?.tool_name).toBe("Write");
    });

    it("ignores event if no sub agent ref", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({ type: "sub_agent_tool_use", agent_name: "coder", tool_name: "Write", tool_input: { path: "/b.ts" } }, refs, cb);

      expect(cb.getItems()).toHaveLength(0);
    });
  });

  describe("sub_agent_tool_result", () => {
    it("attaches result to last sub agent tool", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({ type: "sub_agent_assistant_text", agent_name: "coder", content: "x" }, refs, cb);
      handleEvent({ type: "sub_agent_tool_use", agent_name: "coder", tool_name: "Write", tool_input: { path: "/b.ts" } }, refs, cb);
      handleEvent({ type: "sub_agent_tool_result", agent_name: "coder", content: "ok" }, refs, cb);

      expect(refs.subAgentRef.current?.toolUses?.[0]?.result).toBe("ok");
    });
  });

  describe("sub_agent_error", () => {
    it("sets error with agent name prefix", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({ type: "sub_agent_error", agent_name: "coder", error: "crash" }, refs, cb);

      expect(cb.getError()).toBe("[coder] crash");
    });
  });

  describe("handoff_done", () => {
    it("finalizes sub agent item and clears ref", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({ type: "sub_agent_assistant_text", agent_name: "coder", content: "Done!" }, refs, cb);
      handleEvent({ type: "handoff_done", agent_name: "coder" }, refs, cb);

      expect(refs.subAgentRef.current).toBeNull();
      const items = cb.getItems();
      expect(items).toHaveLength(1);
      const item = items[0] as HandoffItem;
      expect(item.itemType).toBe("handoff_done");
      expect(item.content).toBe("Done!");
      expect(item.id).not.toBe("__sub_agent_streaming__");
    });

    it("does nothing if no sub agent ref", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({ type: "handoff_done", agent_name: "coder" }, refs, cb);

      expect(cb.getItems()).toHaveLength(0);
    });
  });

  describe("handoff_cycle_detected", () => {
    it("adds cycle item", () => {
      const refs = createMockRefs();
      const cb = createMockCallbacks();

      handleEvent({ type: "handoff_cycle_detected", message: "A -> B -> A" }, refs, cb);

      const items = cb.getItems();
      expect(items).toHaveLength(1);
      const item = items[0] as HandoffItem;
      expect(item.itemType).toBe("handoff_cycle");
      expect(item.agentName).toBe("system");
      expect(item.content).toBe("A -> B -> A");
    });
  });
});
