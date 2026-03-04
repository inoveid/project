import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChatMessage } from "./ChatMessage";
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

describe("ChatMessage", () => {
  it("renders user message with blue background", () => {
    render(<ChatMessage message={makeMessage({ role: "user", content: "Hi there" })} />);
    expect(screen.getByText("Hi there")).toBeInTheDocument();
    const container = screen.getByText("Hi there").closest("div.bg-blue-600");
    expect(container).toBeTruthy();
  });

  it("renders assistant message with white background", () => {
    render(
      <ChatMessage message={makeMessage({ role: "assistant", content: "Hello!" })} />,
    );
    expect(screen.getByText("Hello!")).toBeInTheDocument();
  });

  it("renders tool uses for assistant messages", () => {
    render(
      <ChatMessage
        message={makeMessage({
          role: "assistant",
          content: "Let me read that file.",
          tool_uses: [{ tool_name: "Read", tool_input: { path: "/a.ts" } }],
        })}
      />,
    );
    expect(screen.getByText("Read")).toBeInTheDocument();
  });

  it("does not render tool uses when null", () => {
    render(
      <ChatMessage
        message={makeMessage({ role: "assistant", content: "Done", tool_uses: null })}
      />,
    );
    expect(screen.getByText("Done")).toBeInTheDocument();
  });
});
