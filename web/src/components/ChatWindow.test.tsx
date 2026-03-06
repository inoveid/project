import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChatWindow } from "./ChatWindow";
import type { ChatItem, HandoffItem, Message } from "../types";

function makeMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: "msg-1",
    session_id: "session-1",
    role: "user",
    content: "Hello",
    tool_uses: null,
    created_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeHandoffItem(overrides: Partial<HandoffItem> = {}): HandoffItem {
  return {
    id: "handoff-1",
    itemType: "handoff_start",
    agentName: "Reviewer",
    fromAgent: "Developer",
    toAgent: "Reviewer",
    content: "Review task",
    created_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("ChatWindow", () => {
  it("shows empty state when no items", () => {
    render(<ChatWindow items={[]} />);
    expect(screen.getByText(/No messages yet/)).toBeInTheDocument();
  });

  it("renders messages", () => {
    const items: ChatItem[] = [
      makeMessage({ id: "1", role: "user", content: "Hi" }),
      makeMessage({ id: "2", role: "assistant", content: "Hello!" }),
    ];
    render(<ChatWindow items={items} />);
    expect(screen.getByText("Hi")).toBeInTheDocument();
    expect(screen.getByText("Hello!")).toBeInTheDocument();
  });

  it("renders handoff block for handoff items", () => {
    const items: ChatItem[] = [
      makeHandoffItem({
        id: "h1",
        itemType: "handoff_start",
        fromAgent: "Developer",
        toAgent: "Reviewer",
      }),
    ];
    render(<ChatWindow items={items} />);
    expect(screen.getByText(/Developer → Reviewer/)).toBeInTheDocument();
  });

  it("renders chat message for message items", () => {
    const items: ChatItem[] = [
      makeMessage({ id: "m1", role: "user", content: "User question" }),
    ];
    render(<ChatWindow items={items} />);
    expect(screen.getByText("User question")).toBeInTheDocument();
  });
});
