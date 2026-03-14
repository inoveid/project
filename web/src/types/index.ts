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

export interface AgentPrompt {
  name: string;
  content: string;
}

export interface SubAgentTemplate {
  id: string;
  role: string;
  name: string;
  system_prompt: string;
  allowed_tools: string[];
  max_budget_usd: number;
  description: string;
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
  sub_agent_templates: SubAgentTemplate[];
  max_cycles: number;
  can_complete_task: boolean;
  position_x: number | null;
  position_y: number | null;
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
  sub_agent_templates?: SubAgentTemplate[];
  can_complete_task?: boolean;
}

export interface AgentUpdate {
  name?: string;
  role?: string;
  description?: string | null;
  system_prompt?: string;
  allowed_tools?: string[];
  config?: Record<string, unknown>;
  sub_agent_templates?: SubAgentTemplate[];
  max_cycles?: number;
  can_complete_task?: boolean;
  position_x?: number | null;
  position_y?: number | null;
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
  | { type: "stop" }
  | { type: "approve" }
  | { type: "refine"; comment: string };

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
  | { type: "error"; error: string }
  | { type: "handoff_start"; from_agent: string; to_agent: string; task: string }
  | { type: "handoff_cycle_detected"; message: string }
  | { type: "status"; status: string }
  | { type: "approval_required"; from_agent: string; to_agent: string; task: string; chain?: string[][]; steps?: { agent: string; summary: string }[]; workflow_agents?: string[] }
  | { type: "sub_agent_spawned"; sub_session_id: string; role: string; name: string; task: string }
  | { type: "sub_agent_assistant_text"; sub_session_id: string; sub_agent_name: string; sub_agent_role: string; content: string }
  | { type: "sub_agent_tool_use"; sub_session_id: string; sub_agent_name: string; tool_name: string; tool_input: Record<string, unknown> }
  | { type: "sub_agent_tool_result"; sub_session_id: string; sub_agent_name: string; content: string }
  | { type: "sub_agent_done"; sub_session_id: string; role: string; name: string; output_preview: string }
  | { type: "sub_agent_error"; sub_session_id: string; role: string; name: string; error: string };

export interface HandoffItem {
  id: string;
  itemType: "handoff_start" | "handoff_cycle" | "approval_required" | "activity";
  agentName: string;
  fromAgent?: string;
  toAgent?: string;
  content: string;
  toolUses?: ToolUse[];
  created_at: string;
}

export type ChatItem = Message | HandoffItem;

export function isHandoffItem(item: ChatItem): item is HandoffItem {
  return "itemType" in item;
}

export interface ApprovalRequest {
  fromAgent: string;
  toAgent: string;
  task: string;
  chain?: string[][];
  steps?: { agent: string; summary: string }[];
  workflowAgents?: string[];
}

// ── Evaluation types ────────────────────────────────────────────────────────

export interface RubricCriterion {
  name: string;
  description: string;
  weight: number;
  pass_threshold: number;
}

export interface EvalCase {
  id: string;
  name: string;
  description: string;
  agent_role: string;
  task_prompt: string;
  context_files: Record<string, string>;
  rubric: RubricCriterion[];
  expected_artifacts: string[];
  tags: string[];
  created_at: string;
}

export interface EvalCaseCreate {
  name: string;
  description: string;
  agent_role?: string;
  task_prompt: string;
  context_files?: Record<string, string>;
  rubric: RubricCriterion[];
  expected_artifacts?: string[];
  tags?: string[];
}

export interface EvalRunSummary {
  id: string;
  name: string;
  prompt_version: string;
  model: string;
  status: "pending" | "running" | "completed" | "failed";
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  pass_rate: number | null;
  created_at: string;
}

export interface EvalRun extends EvalRunSummary {
  prompt_snapshot: string;
  metadata_: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
}

export interface EvalRunCreate {
  name: string;
  prompt_version: string;
  prompt_snapshot: string;
  model?: string;
  case_ids?: string[];
  metadata?: Record<string, unknown>;
}

export interface CriterionScore {
  score: number;
  reasoning: string;
}

export interface EvalResult {
  id: string;
  run_id: string;
  case_id: string;
  agent_output: string;
  verdict: "pass" | "fail" | "error";
  score: number;
  criteria_scores: Record<string, CriterionScore>;
  judge_reasoning: string;
  trajectory: Record<string, unknown>;
  token_usage: Record<string, number>;
  duration_ms: number | null;
  created_at: string;
}

export interface Business {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  products_count: number;
}

export interface BusinessCreate {
  name: string;
  description?: string;
}

export interface BusinessUpdate {
  name?: string;
  description?: string;
}

export interface Product {
  id: string;
  business_id: string;
  name: string;
  description: string | null;
  git_url: string | null;
  workspace_path: string;
  status: 'pending' | 'cloning' | 'ready' | 'error';
  clone_error: string | null;
  created_at: string;
}

export interface ProductCreate {
  name: string;
  description?: string;
  git_url?: string;
  business_id: string;
}

export interface ProductUpdate {
  name?: string;
  description?: string;
  git_url?: string;
}

// ── Task types ──────────────────────────────────────────────────────────────

export type TaskStatus = 'backlog' | 'in_progress' | 'awaiting_user' | 'done' | 'error';

export interface Task {
  id: string;
  title: string;
  description: string | null;
  product_id: string | null;
  team_id: string | null;
  workflow_id: string | null;
  spec_id: string | null;
  status: TaskStatus;
  error_message: string | null;
  created_at: string;
}

export interface TaskCreate {
  title: string;
  description?: string;
  product_id?: string;
  team_id?: string;
  workflow_id?: string;
  spec_id?: string;
}

export interface TaskUpdate {
  title?: string;
  description?: string;
  product_id?: string;
  team_id?: string;
  workflow_id?: string;
  spec_id?: string;
}

export interface TaskStatusUpdate {
  status: TaskStatus;
}

const TASK_STATUSES: ReadonlySet<string> = new Set<TaskStatus>([
  'backlog', 'in_progress', 'awaiting_user', 'done', 'error',
]);

export function isTaskStatus(value: unknown): value is TaskStatus {
  return typeof value === 'string' && TASK_STATUSES.has(value);
}

export function isTask(value: unknown): value is Task {
  if (typeof value !== 'object' || value === null) return false;
  if (!('id' in value) || !('title' in value) || !('status' in value)) return false;
  const { id, title, status } = value as Task;
  return typeof id === 'string' && typeof title === 'string' && isTaskStatus(status);
}

export interface EvalComparison {
  run_a: { id: string; prompt_version: string | null; pass_rate: number | null };
  run_b: { id: string; prompt_version: string | null; pass_rate: number | null };
  common_cases: number;
  regressions: Array<{ case_id: string; score_a: number; score_b: number; delta: number }>;
  improvements: Array<{ case_id: string; score_a: number; score_b: number; delta: number }>;
  regression_count: number;
  improvement_count: number;
}

// ── Workflow types ──────────────────────────────────────────────────────────

export interface Workflow {
  id: string;
  name: string;
  description: string | null;
  team_id: string;
  starting_agent_id: string;
  starting_prompt: string;
  isolation_mode: "none" | "worktree";
  created_at: string;
  updated_at: string;
}

export interface WorkflowCreate {
  name: string;
  starting_agent_id: string;
  starting_prompt: string;
  description?: string | null;
}

export interface WorkflowUpdate {
  name?: string;
  description?: string | null;
  starting_agent_id?: string;
  starting_prompt?: string;
  isolation_mode?: "none" | "worktree";
}

export interface WorkflowEdge {
  id: string;
  workflow_id: string;
  from_agent_id: string;
  to_agent_id: string;
  condition: string | null;
  prompt_template: string | null;
  order: number;
  requires_approval: boolean;
  max_rounds: number;
  created_at: string;
}

export interface WorkflowEdgeCreate {
  from_agent_id: string;
  to_agent_id: string;
  condition?: string | null;
  prompt_template?: string | null;
  order?: number;
  requires_approval?: boolean;
  max_rounds?: number;
}

export interface WorkflowEdgeUpdate {
  condition?: string | null;
  prompt_template?: string | null;
  order?: number;
  requires_approval?: boolean;
  max_rounds?: number;
}

// ── Canvas validation types ─────────────────────────────────────────────────

export interface AgentCanDeleteResponse {
  can_delete: boolean;
  reason: string | null;
}

export interface ValidationIssue {
  type: 'error' | 'warning' | 'info';
  message: string;
  nodeId?: string;
  workflowId?: string;
}

// ── Spec types ──────────────────────────────────────────────────────────────

export type SpecStatus = 'draft' | 'active';

export interface Spec {
  id: string;
  product_id: string;
  feature: string;
  title: string;
  content: string;
  version: number;
  status: SpecStatus;
  created_at: string;
  updated_at: string;
}

export interface SpecCreate {
  feature: string;
  title: string;
  content?: string;
  status?: SpecStatus;
}

export interface SpecUpdate {
  feature?: string;
  title?: string;
  content?: string;
  status?: SpecStatus;
  author?: string;
  summary?: string;
}

export interface SpecVersion {
  id: string;
  spec_id: string;
  version: number;
  content: string;
  author: string;
  summary: string | null;
  created_at: string;
}
