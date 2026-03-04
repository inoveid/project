import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChatWindow } from "./ChatWindow";
import type { Message } from "../types";

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

describe("ChatWindow", () => {
  it("shows empty state when no messages", () => {
    render(<ChatWindow messages={[]} />);
    expect(screen.getByText(/No messages yet/)).toBeInTheDocument();
  });

  it("renders messages", () => {
    const messages = [
      makeMessage({ id: "1", role: "user", content: "Hi" }),
      makeMessage({ id: "2", role: "assistant", content: "Hello!" }),
    ];
    render(<ChatWindow messages={messages} />);
    expect(screen.getByText("Hi")).toBeInTheDocument();
    expect(screen.getByText("Hello!")).toBeInTheDocument();
  });
});
