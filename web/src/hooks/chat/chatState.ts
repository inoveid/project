import type { MutableRefObject } from "react";
import type { ApprovalRequest, ChatItem, Message, ToolUse } from "../../types";

export type ChatStatus = "idle" | "connecting" | "connected" | "typing" | "tool" | "disconnected" | "awaiting_approval";

export interface UseChatResult {
  items: ChatItem[];
  messages: Message[];
  status: ChatStatus;
  error: string | null;
  pendingApproval: ApprovalRequest | null;
  sendMessage: (content: string) => void;
  stopAgent: () => void;
  approveHandoff: () => void;
  rejectHandoff: () => void;
}

export interface PendingRefs {
  textRef: MutableRefObject<string>;
  toolsRef: MutableRefObject<ToolUse[]>;
}

export function makeLocalMessage(role: "user" | "assistant", content: string): Message {
  return {
    id: crypto.randomUUID(),
    session_id: "",
    role,
    content,
    tool_uses: null,
    created_at: new Date().toISOString(),
  };
}

export const RECONNECT_BASE_DELAY_MS = 1000;
export const MAX_RECONNECT_ATTEMPTS = 20;
