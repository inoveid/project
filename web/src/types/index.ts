export interface Team {
  id: string;
  name: string;
  description: string | null;
  project_scoped: boolean;
  created_at: string;
  updated_at: string;
  agents_count: number;
  agents?: Agent[];
}

export interface TeamCreate {
  name: string;
  description?: string | null;
  project_scoped?: boolean;
}

export interface TeamUpdate {
  name?: string;
  description?: string | null;
  project_scoped?: boolean;
}

export interface Agent {
  id: string;
  team_id: string;
  name: string;
  role: string;
  description: string | null;
  system_prompt: string;
  allowed_tools: string[];
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AgentCreate {
  name: string;
  role: string;
  description?: string | null;
  system_prompt: string;
  allowed_tools?: string[];
  config?: Record<string, unknown>;
}

export interface AgentUpdate {
  name?: string;
  role?: string;
  description?: string | null;
  system_prompt?: string;
  allowed_tools?: string[];
  config?: Record<string, unknown>;
}

export interface AgentLink {
  id: string;
  team_id: string;
  from_agent_id: string;
  to_agent_id: string;
  link_type: "handoff" | "review" | "migration_brief";
  created_at: string;
}

export interface Session {
  id: string;
  agent_id: string;
  status: "active" | "stopped";
  claude_session_id: string | null;
  created_at: string;
  stopped_at: string | null;
  messages?: Message[];
}

export interface ToolUse {
  tool_name: string;
  tool_input: Record<string, unknown>;
  result?: string;
}

export interface Message {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  tool_uses: ToolUse[] | null;
  created_at: string;
}

export interface SessionListItem {
  id: string;
  agent_id: string;
  agent_name: string;
  status: "active" | "stopped";
  created_at: string;
  stopped_at: string | null;
}

export type WsOutgoing =
  | { type: "message"; content: string }
  | { type: "stop" };

export interface AuthStatus {
  logged_in: boolean;
  email: string | null;
  org_name: string | null;
  subscription_type: string | null;
  auth_method: string | null;
}

export interface AuthLoginResponse {
  auth_url: string;
  message: string;
}

export interface AuthCodeSubmit {
  code: string;
}

export type WsIncoming =
  | { type: "assistant_text"; content: string }
  | { type: "tool_use"; tool_name: string; tool_input: Record<string, unknown> }
  | { type: "tool_result"; content: string }
  | { type: "done" }
  | { type: "error"; error: string };
