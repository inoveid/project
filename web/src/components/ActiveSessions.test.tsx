import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ActiveSessions } from "./ActiveSessions";
import type { SessionListItem } from "../types";

const mockSession: SessionListItem = {
  id: "session-1",
  agent_id: "agent-1",
  agent_name: "Code Agent",
  status: "active",
  created_at: "2024-01-15T10:30:00Z",
  stopped_at: null,
};

describe("ActiveSessions", () => {
  it("renders empty state when no sessions", () => {
    render(<ActiveSessions sessions={[]} onOpenChat={vi.fn()} />);
    expect(screen.getByText("No active sessions")).toBeInTheDocument();
  });

  it("renders session with agent name", () => {
    render(
      <ActiveSessions sessions={[mockSession]} onOpenChat={vi.fn()} />,
    );
    expect(screen.getByText("Code Agent")).toBeInTheDocument();
  });

  it("calls onOpenChat when button clicked", () => {
    const onOpenChat = vi.fn();
    render(
      <ActiveSessions sessions={[mockSession]} onOpenChat={onOpenChat} />,
    );
    fireEvent.click(screen.getByText("Open Chat"));
    expect(onOpenChat).toHaveBeenCalledWith("session-1");
  });

  it("renders multiple sessions", () => {
    const sessions: SessionListItem[] = [
      mockSession,
      { ...mockSession, id: "session-2", agent_name: "Review Agent" },
    ];
    render(<ActiveSessions sessions={sessions} onOpenChat={vi.fn()} />);
    expect(screen.getByText("Code Agent")).toBeInTheDocument();
    expect(screen.getByText("Review Agent")).toBeInTheDocument();
  });
});
