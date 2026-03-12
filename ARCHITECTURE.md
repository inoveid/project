# ARCHITECTURE.md

Архитектурная карта проекта Agent Console. Источник истины — текущий код.
Конвенции, команды и структура каталогов — см. [CLAUDE.md](CLAUDE.md).

---

## 1. Карта модулей

```
┌──────────────────────────────────────────────────────────────────┐
│                     Frontend (React + Vite)                      │
│                                                                  │
│  Pages (9)           Hooks (31)            API Layer (11)        │
│  ┌──────────────┐   ┌────────────────┐    ┌──────────────┐      │
│  │ Dashboard    │──→│ useTeams       │──→ │ teams.ts     │──┐   │
│  │  (Kanban)    │   │ useAgents      │    │ agents.ts    │  │   │
│  │ CanvasPage   │   │ useSessions    │    │ sessions.ts  │  │   │
│  │ ChatPage     │   │ useAuth        │    │ auth.ts      │  │   │
│  │ EvalDashboard│   │ useAgentLinks  │    │ eval.ts      │  │   │
│  │ BusinessList │   │ useBusinesses  │    │ agentLinks.ts│  │   │
│  │ BusinessPage │   │ useProducts    │    │ businesses.ts│  │   │
│  │ TeamPage     │   │ useEvaluations │    │ products.ts  │  │   │
│  └──────────────┘   │ useSystemAgent │    │ tasks.ts     │  │   │
│       │             │ useTasks       │    │ workflows.ts │  │   │
│       ▼             │ useWorkflows   │    └──────────────┘  │   │
│  Components (82)    │ useCanvasData  │                      │   │
│  ┌──────────────┐   │ useCanvasMut.  │                      │   │
│  │ ChatPanel    │──→│ useWfValidation│                      │   │
│  │ ChatWindow   │   │ useWfLock      │                      │   │
│  │ MiniChatWindow│  │ useAutoSave    │                      │   │
│  │ HandoffBlock │   │ useAgentDelet. │                      │   │
│  │ SessionList  │   │ useToast       │                      │   │
│  │ TaskCard     │   │ useNotifSocket │                      │   │
│  │ KanbanColumn │   └────────────────┘                      │   │
│  │ TaskModal    │   ┌────────────────┐                      │   │
│  │ canvas/*     │──→│ useChat (пакет)│──── WebSocket ───────┼─┐ │
│  │ notifications│   │  13 WS events  │                      │ │ │
│  └──────────────┘   └────────────────┘                      │ │ │
│                                                             │ │ │
│  GlobalChatWidget + MiniChatWindow (fixed bottom-right)     │ │ │
│    └─ useSystemAgent (localStorage session) + useAuth       │ │ │
│                                                             │ │ │
│  NotificationLayer + ToastContainer (fixed top-right)       │ │ │
│    └─ useNotificationSocket (/api/ws/notifications)         │ │ │
│                                                             │ │ │
│  Types: types/index.ts (48 type declarations)               │ │ │
└─────────────────────────────────────────────────────────────┼─┼─┘
                                                              │ │
                               HTTP REST ─────────────────────┘ │
                               WebSocket ───────────────────────┘
                                                              │ │
┌─────────────────────────────────────────────────────────────┼─┼─┐
│                     Backend (FastAPI)                        │ │ │
│                                                             ▼ ▼ │
│  Routers (13)               Services (24+)                      │
│  ┌───────────────┐         ┌──────────────────────────────┐     │
│  │ teams.py      │────────→│ team_service                 │     │
│  │ agents.py     │────────→│ agent_service                │     │
│  │ sessions.py   │────────→│ session_service              │     │
│  │ workflows.py  │────────→│ workflow_service              │     │
│  │ wf_edges.py   │────────→│ workflow_edge_service         │     │
│  │ auth.py       │────────→│ auth_service                 │     │
│  │ memory.py     │────────→│ memory_service               │     │
│  │ evaluations.py│────────→│ eval_service → judge_service │     │
│  │ businesses.py │────────→│ business_service             │     │
│  │ products.py   │────────→│ product_service              │     │
│  │ tasks.py      │────────→│ task_service                 │     │
│  │               │         │ system_agent_service          │     │
│  └───────────────┘         └──────────────────────────────┘     │
│                                                                  │
│  ┌───────────────┐         ┌──────────────────────────────┐     │
│  │ ws.py         │─Redis──→│ worker.py (Task Worker)      │     │
│  │  WS thin proxy│  pub/sub│  EventPublisher → Redis      │     │
│  │  ↔ Redis      │         │  subscribe_commands → graph  │     │
│  │               │         │  try/finally cleanup         │     │
│  │ notif_ws.py   │─Redis──→│                              │     │
│  │  /ws/notif.   │  pub/sub│ graph_service (~501 строк)   │     │
│  └───────────────┘         │  Nodes (6):                  │     │
│                            │  ├─ run_agent (→runtime)     │     │
│  ┌───────────────┐         │  ├─ notify_handoff           │     │
│  │ Redis 7       │         │  ├─ gate (HITL interrupt)    │     │
│  │ event_bus.py  │         │  ├─ auto_handoff             │     │
│  │  pub/sub +    │         │  ├─ complete_node            │     │
│  │  buffer (list)│         │  └─ blocked_node             │     │
│  │ redis_service │         │                              │     │
│  └───────────────┘         │  runtime (Claude Agent SDK)  │     │
│                            │  ├─ budget                   │     │
│                            │  ├─ circuit_breaker          │     │
│                            │  └─ telemetry                │     │
│                            │                              │     │
│                            │  notification_service        │     │
│                            │  (Redis pub/sub wrapper)     │     │
│                            └──────────────────────────────┘     │
│                                       │                         │
│  ┌──────────────────┐                 │                         │
│  │ Models (16 ORM)  │←── SQLAlchemy ──┘                         │
│  │ Schemas (Pydantic)│                                          │
│  └────────┬─────────┘                                           │
│           ▼                                                     │
│  ┌──────────────────┐  ┌────────────────┐                      │
│  │ PostgreSQL       │  │ LangGraph      │                      │
│  │ + pgvector       │  │ Checkpoints    │                      │
│  │ 14 таблиц        │  │ (PostgreSQL)   │                      │
│  └──────────────────┘  └────────────────┘                      │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────┐    ┌─────────────────────┐
│  MCP Server (автономный) │    │  External APIs      │
│  mcp/server.py           │    │  ├─ Claude Agent SDK │
│  mcp/tools/platform.py   │    │  ├─ Claude API       │
│  HTTP → localhost:8000   │    │  │   (judge_service) │
│  ─── stdio ──→ Claude    │    │  ├─ Voyage AI        │
│             Code         │    │  │   (memory_service)│
└──────────────────────────┘    │  └─ Langfuse (opt)   │
                                └─────────────────────┘
```

### Таблица модулей

#### Backend — Services

| Модуль | Строк | Ответственность |
|--------|-------|-----------------|
| graph_service.py | ~501 | LangGraph StateGraph: 6 nodes, 2 routing functions, MCP handoff integration, checkpoint |
| runtime/ (пакет) | ~220 | Claude Agent SDK sessions (ClaudeSDKClient), budget tracking, circuit breaker. 1 модуль: agent_runner |
| handoff_server.py | ~359 | MCP tool-based handoff: generate tools from workflow edges, handle tool calls, max_cycles enforcement, prompt rendering |
| eval_service.py | ~312 | EvalCase/EvalRun CRUD, batch execution, comparison |
| auth_service.py | ~209 | OAuth2 PKCE, token refresh |
| budget.py | ~208 | BudgetTracker, cost computation, warning/critical events |
| memory_service.py | ~199 | pgvector RAG, Voyage AI embeddings |
| judge_service.py | ~198 | LLM-as-Judge via Anthropic SDK |
| workflow_service.py | ~183 | Workflow CRUD, active tasks check, workflow locking, validation |
| circuit_breaker.py | ~151 | CLOSED/OPEN/HALF_OPEN state machine |
| product_service.py | ~110 | Product CRUD, async git clone (fire-and-forget), status lifecycle |
| workflow_edge_service.py | ~109 | WorkflowEdge CRUD, ordered edges |
| task_service.py | ~108 | Task CRUD, status machine (VALID_TRANSITIONS), required fields validation |
| team_service.py | ~107 | Team CRUD |
| agent_link_service.py | ~104 | AgentLink CRUD + routing (legacy, заменён workflow edges) |
| agent_service.py | ~104 | Agent CRUD |
| session_service.py | ~95 | Session + Message CRUD |
| business_service.py | ~90 | Business CRUD, force delete, scalar subquery products_count |
| notification_service.py | ~15 | Convenience wrapper → event_bus.publish_notification() |
| event_bus.py | ~130 | Redis pub/sub абстракция: publish/subscribe events, commands, notifications + event buffer (Redis list) для WS reconnection replay |
| redis_service.py | ~30 | Redis connection pool singleton (init/close/get), используется event_bus и ws.py |
| worker.py | ~460 | Task Worker — отдельный процесс: слушает Redis commands, запускает LangGraph граф, публикует events через EventPublisher. try/finally cleanup |
| utils/handoff.py | ~50 | format_handoff_instructions, parse_handoff_block, build_agent_prompt |
| system_agent_service.py | ~25 | System Agent seed (idempotent) |
| telemetry.py | ~25 | Langfuse init wrapper |

#### Backend — Routers

| Модуль | Endpoints | Особенности |
|--------|-----------|-------------|
| ws.py | 1 WS | Thin proxy: WS ↔ Redis Event Bus. Subscribe-before-buffer replay для reconnection |
| notifications_ws.py | 1 WS | Redis pub/sub → WS forward (subscribe_notifications) |
| evaluations.py | 8 REST | Background task execution |
| memory.py | 3 REST | Inline Pydantic schemas |
| agents.py | 7 REST | /agents + /teams/{id}/agents + /agents/system + /agents/{id}/can-delete |
| workflows.py | 5+ REST | /teams/{id}/workflows + /workflows/{id} + /workflows/{id}/active-tasks |
| workflow_edges.py | 4 REST | /workflows/{id}/edges CRUD |
| businesses.py | 5 REST | Business CRUD (force delete support) |
| products.py | 6 REST | Product CRUD + POST /clone (fire-and-forget) |
| tasks.py | 7 REST | Task CRUD + PATCH /status (state machine) |
| teams.py | 5 REST | Standard CRUD |
| agent_links.py | 3 REST | Team-scoped (legacy) |
| sessions.py | 4 REST | Status lifecycle |
| auth.py | 4 REST | OAuth PKCE flow |

#### Backend — Models & Schemas

16 ORM-моделей: Team (+ workflows rel.), Agent (+ is_system, nullable team_id/role, JSONB prompts, max_cycles, position_x/y), AgentLink (legacy), Workflow (+ starting_agent_id RESTRICT, starting_prompt, edges rel.), WorkflowEdge (+ from/to_agent_id CASCADE, condition, prompt_template, requires_approval, max_cycles, order), Session (+ task_id FK), Message, OAuthToken, EpisodicMemory, SemanticMemory, EvalCase, EvalRun, EvalResult, Business, Product, Task (+ CHECK constraint on status).

Pydantic-схемы: паттерн `{Resource}Create`, `{Resource}Update`, `{Resource}Read`. Pydantic v2, `from_attributes=True`.

#### Frontend

| Категория | Файлов | Ключевые |
|-----------|--------|----------|
| Pages | 9 | Dashboard (Kanban), CanvasPage (ReactFlow), ChatPage, EvalDashboard, BusinessListPage, BusinessPage, TeamPage |
| Hooks | 31 | useChat (пакет `hooks/chat/`, 8 файлов), useTasks, useWorkflows, useCanvasData, useCanvasMutations, useWorkflowValidation, useWorkflowLock, useAutoSave, useToast, useNotificationSocket, useAgentDeletable, useAuth, useSystemAgent, useBusinesses, useProducts, useEvaluations, useAgents и др. |
| Components | 82 | 39 root (ChatPanel, TaskCard, KanbanColumn и др.) + canvas/ (17, AgentNode, TeamGroupNode, SidePanel и др.) + tasks/ (16, CreateTaskModal, TaskModal, FilterBar и др.) + eval/ (4) + notifications/ (3, ToastContainer, NotificationLayer) |
| API Layer | 11 | client.ts (экспортирует BASE_URL) + 10 resource modules (tasks.ts, workflows.ts добавлены) |
| Types | 1 | 48 type declarations (44 interfaces + 4 type aliases), 13+ WS event types |

#### MCP Server (автономный, stdio)

| Файл | Ответственность |
|------|-----------------|
| mcp/server.py | FastMCP регистрация platform tools, точка входа (`python mcp/server.py`) |
| mcp/tools/platform.py | 8 инструментов: list/create businesses, products, teams, agents. HTTP → `settings.api_base_url` |

**Важно:** `mcp/tools/platform.py` импортирует `app.config.settings` (зависимость от FastAPI-конфигурации). Пакет `api/mcp/` конфликтует с PyPI-пакетом `mcp` по имени — FastMCP импортируется только через `TYPE_CHECKING`.

#### Handoff Server (handoff_server.py, ~359 строк)

| Класс/Функция | Ответственность |
|----------------|-----------------|
| `HandoffTool` | Dataclass: tool name, description, to_agent, requires_approval, edge_id, prompt_template |
| `HandoffResultType` (Enum) | FORWARDED, AWAITING_APPROVAL, BLOCKED, COMPLETED |
| `HandoffResult` | Dataclass: result_type, reason, to_agent_id/name, prompt, edge_id |
| `generate_handoff_tools(db, agent_id, workflow_id)` | Создаёт MCP tools из исходящих WorkflowEdge + "complete_task" tool для терминальных агентов |
| `format_handoff_tools_prompt(tools)` | Форматирует tools как system prompt инструкции для агента |
| `handle_handoff_tool_call(db, tool_name, tool_args, tools, task_id, agent_id)` | Валидирует tool, проверяет max_cycles, возвращает HandoffResult |
| `parse_handoff_from_text(text)` | Извлекает ` ```handoff {...}``` ` JSON-блок из текста агента |
| `count_agent_visits(db, task_id, agent_id)` | Считает визиты агента через Session count |
| `render_prompt(template, task)` | Подставляет `{{task_title}}`, `{{task_description}}` |

**Naming convention:** tool name = snake_case от edge condition, или `forward_to_{agent_name}`.

---

## 2. Потоки данных

### 2.1 CRUD flow

```
Client HTTP request
  → Router (teams/agents/sessions/agent_links.py)
    → Service (CRUD functions, принимает AsyncSession + Pydantic schema)
      → SQLAlchemy ORM
        → PostgreSQL
  ← Response (Pydantic Read schema)
```

**Файлы:** model → schema → service → router → main.py (5 файлов на ресурс).

Change isolation: **высокая** — каждый ресурс изолирован.

### 2.2 Chat flow

Архитектура: **WS (thin proxy) → Redis Event Bus → Task Worker → Claude Agent SDK**.

```
┌─────────┐    WS     ┌──────────┐   Redis pub/sub   ┌──────────────┐
│  Client  │◄────────►│  ws.py   │◄─────────────────►│  worker.py   │
│ (browser)│          │ (proxy)  │   events/commands  │ (Task Worker)│
└─────────┘           └──────────┘                    └──────┬───────┘
                           │                                 │
                           │                     ┌───────────▼──────────┐
                      Redis buffer               │  LangGraph + SDK     │
                      (replay on                 │  graph_service.py    │
                       reconnect)                │  runtime (Agent SDK) │
                                                 └──────────────────────┘
```

**Последовательность:**
```
1. Client → WS connect /api/ws/sessions/{session_id}
2. ws.py (thin proxy): accept → validate session → notify Worker (Redis publish worker:sessions)
3. ws.py: subscribe to Redis pub/sub session:{id}:events BEFORE reading buffer
   → replay buffered events (Redis list) → forward live events to WS
4. Worker (handle_session → _run_session):
   a. Load session, agent, resolve workdir (product.workspace_path → agent.config → default)
   b. Auto-create workspace dir + git init if needed
   c. If task+workflow → generate_handoff_tools → append to system_prompt
   d. runtime.start_session() → сохраняет AgentSession (SDK config, не subprocess)
   e. Subscribe to Redis commands, listen for messages
5. Client sends {"type": "message", "content": "..."}
   → ws.py publishes to Redis session:{id}:commands
   → Worker receives command
6. Worker: add_message(db, user) → build WorkflowState → _run_graph()
7. graph.astream() → run_agent_node:
     a. runtime.send_message():
        → get OAuth token (auth_service)
        → check budget + circuit_breaker
        → ClaudeSDKClient.connect() → query(content)
        → stream typed Python objects (AssistantMessage, StreamEvent, ResultMessage)
        → record budget usage
        → yield events (assistant_text, tool_use, tool_result)
     b. EventPublisher.send_json(event) → Redis pub/sub → ws.py → Client
        — depth > 0: события получают prefix sub_agent_
     c. save response to DB (add_message assistant)
     d. parse_handoff_from_text → handle_handoff_tool_call → HandoffResult
     e. depth > 0: runtime.stop_session() (disconnect SDK client)
        depth == 0: сохраняет claude_session_id для resume
8-15. (routing, handoff, gate — без изменений, см. §4 LangGraph Workflow)
16. Worker: publish {"type": "done"} → Redis → ws.py → Client
17. Worker cleanup (try/finally): stop children, stop runtime, clear buffer
```

**Ключевые отличия от старой архитектуры:**
- ws.py — **тонкий прокси** (~91 строк), не содержит бизнес-логику
- Graph execution в **отдельном процессе** (worker.py), WS disconnect НЕ останавливает Worker
- Runtime использует **Claude Agent SDK** (typed Python API) вместо subprocess + stdout parsing
- Events буферизуются в **Redis list** (500 events, 1h TTL) для reconnection replay
- `product_workspace` пропагируется через WorkflowState для изоляции проектов

**Файлы (14+):** ws.py (proxy), worker.py, event_bus.py, redis_service.py, graph_service.py, handoff_server.py, runtime/ (agent_runner.py), notification_service.py, utils/handoff.py, auth_service.py, budget.py, circuit_breaker.py, session_service.py, task_service.py.

Change isolation: **средняя** — ws.py изолирован как прокси; worker.py содержит orchestration; graph_service и runtime — ядро.

### 2.3 Memory flow

```
1. Agent tool call → POST /api/memory/search
2. memory router → memory_service.search_memory()
3. _embed(query) → asyncio.to_thread(voyageai.Client.embed)
4. _search_episodic() + _search_semantic() → pgvector cosine distance
5. merge + sort by similarity → response
```

**Файлы:** memory router, memory_service, memory models (3 файла).

Change isolation: **высокая**.

### 2.4 Evaluation flow

```
1. POST /api/eval/runs → evaluations router
2. eval_service.execute_eval_run() (BackgroundTask)
3. load EvalCases from DB
4. for each case:
     a. get agent output (provider or mock)
     b. judge_service.judge_agent_output() → Anthropic API (Claude)
     c. parse rubric scores, compute weighted average
     d. save EvalResult to DB
5. update EvalRun stats (passed/failed/pass_rate) → done
```

**Файлы:** evaluations router, eval_service, judge_service, eval schemas (4 файла).

Change isolation: **средняя** (зависит от внешнего Claude API).

### 2.5 Product clone polling flow

```
1. Client: POST /api/products/{id}/clone → status="cloning" (немедленно)
2. Frontend: useCloneProduct() мутирует, setQueryData → status="cloning" в кеше
3. ProductCard: передаёт polling=true в useProduct(id, polling=true)
4. useProduct: refetchInterval = (query) => query.state.data?.status === 'cloning' ? 2000 : false
   → polling каждые 2 сек пока status === 'cloning'
   → автоматически останавливается когда status становится 'ready' или 'error'
5. Сервер (backend): _do_clone() обновляет status в БД асинхронно
```

**Файлы:** api/products.ts, hooks/useProducts.ts, components/ProductCard.tsx, api/app/services/product_service.py.

Change isolation: **высокая** — polling изолирован в useProduct, не влияет на другие хуки.



### 2.6 Task lifecycle flow

```
1. Dashboard (Kanban): User creates task via CreateTaskModal
   → POST /api/tasks {title, description, product_id, team_id, workflow_id}
   → task.status = "backlog"
2. User drags task to "In Progress" or clicks "Start" on TaskCard
   → PATCH /api/tasks/{id}/status {status: "in_progress"}
   → task_service validates VALID_TRANSITIONS + REQUIRED_FOR_IN_PROGRESS
   → creates session via ws.py → connects to agent
3. During chat: worker.py auto-updates task status:
   → interrupt (approval_required) → task.status = "awaiting_user"
   → approve → task.status = "in_progress"
   → error → task.status = "error"
   → complete_node → task.status = "done" (via broadcast)
4. User can manually drag done→in_progress (retry) or error→in_progress
```

**Status machine (task_service.py):**
```
backlog → in_progress (requires: title, description, product_id, team_id, workflow_id)
in_progress → awaiting_user | done | error
awaiting_user → in_progress | error
done → in_progress
error → in_progress
```

**Файлы:** task_service.py, tasks.py (router), worker.py (auto-update), Dashboard.tsx, TaskCard.tsx, KanbanColumn.tsx, CreateTaskModal.tsx.

Change isolation: **средняя** — task_service изолирован, но auto-update в worker.py тесно связан с chat flow.

### 2.7 Canvas / Workflow flow

```
1. CanvasPage loads: GET /api/teams → GET /api/teams/{id}/agents (для каждой team)
   → GET /api/teams/{id}/workflows → GET /api/workflows/{wf_id}/edges
2. useCanvasData transforms data → ReactFlow nodes + edges:
   → Team → TeamGroupNode (group container)
   → Agent → AgentNode (child of team, position from position_x/y or auto-layout)
   → WorkflowEdge → custom WorkflowEdge component (directed, colored by workflow)
3. WorkflowFilter dropdown → show all edges or filter by selected workflow
4. useWorkflowValidation continuously validates:
   → Error: workflow without starting_prompt
   → Warning: unreachable agent (no incoming edges)
   → Info: team without agents/workflows
5. useWorkflowLock checks active tasks:
   → GET /api/workflows/{id}/active-tasks
   → If in_progress/awaiting_user tasks exist → workflow locked (read-only)
   → Drag positions still allowed, edge/settings editing blocked
```

**Файлы:** CanvasPage.tsx, components/canvas/ (17 файлов), useCanvasData.ts, useCanvasMutations.ts, useWorkflowValidation.ts, useWorkflowLock.ts, workflows.ts (API).

Change isolation: **высокая** — Canvas изолирован от chat flow, только читает данные.

### 2.8 Notification broadcast flow

```
1. Client → WS connect /api/ws/notifications
   → notifications_ws.py: subscribes to Redis pub/sub (subscribe_notifications)
   → forwards events from Redis → WS
2. Backend events trigger broadcast (through Redis):
   → worker.py / graph_service: approval_required, task_completed, max_cycles_reached, task_error
   → event_bus.publish_notification(event_type, data) → Redis channel "notifications"
3. notification_service.broadcast_notification() — convenience wrapper → event_bus
4. Frontend: useNotificationSocket receives event
   → notificationEventHandler maps to toast:
     → approval_required → warning toast (duration=0, requires action)
     → task_completed → success toast (5s auto-dismiss)
     → task_error → error toast (duration=0)
     → max_cycles_reached → error toast (duration=0)
5. ToastContainer renders toasts (fixed top-right)
```

**Файлы:** notification_service.py, event_bus.py, notifications_ws.py, useNotificationSocket.ts, notificationEventHandler.ts, useToast.tsx, ToastContainer.tsx, NotificationLayer.tsx.

Change isolation: **высокая** — notification система изолирована, fire-and-forget через Redis pub/sub.

### 2.9 GlobalChatWidget flow

```
1. App.tsx рендерит <GlobalChatWidget /> вне <Routes> (все страницы)
2. useAuthStatus() — GET /api/auth/status каждые 10 сек (из useAuth.ts)
   → logged_in === false → disabled кнопка (tooltip)
   → logged_in === true → активный виджет
3. useSystemAgent():
   a. useQuery GET /api/agents/system → systemAgent.id
   b. localStorage.getItem("system_agent_session_id")
      → есть: GET /api/sessions/{id} → ок → использовать
              → 404 → localStorage.removeItem → создать новую
      → нет: POST /api/sessions {agent_id: systemAgent.id} → сохранить в localStorage
4. Кнопка открывает/закрывает MiniChatWindow (400×560px, fixed bottom-24 right-6)
5. При открытии: useQuery GET /api/sessions/{sessionId} → session.messages
   → useChat(sessionId, initialMessages, enabled=true) → WS /api/ws/sessions/{id}
6. Кнопка "Очистить контекст":
   → confirm dialog → resetSession() → localStorage.removeItem
   → useSystemAgent перезапускает инициализацию → новая сессия
```

**Файлы:** GlobalChatWidget.tsx, MiniChatWindow.tsx, hooks/useSystemAgent.ts, hooks/useAuth.ts, api/agents.ts (getSystemAgent).

Change isolation: **высокая** — виджет изолирован через `fixed` позиционирование, не влияет на layout страниц. useSystemAgent не затрагивает другие хуки.

---

## 3. WebSocket Protocol

Endpoint: `WS /api/ws/sessions/{session_id}`

### 3.1 Исходящие от клиента (WsOutgoing)

| Тип | Когда отправляется | Payload |
|-----|--------------------|---------|
| `message` | Пользователь отправляет текст | `{ type: "message", content: string }` |
| `stop` | Пользователь останавливает агента | `{ type: "stop" }` |
| `approve` | HITL: одобрить handoff | `{ type: "approve" }` |
| `reject` | HITL: отклонить handoff | `{ type: "reject" }` |

Типы определены: `web/src/types/index.ts` (`WsOutgoing`), обработка: ws.py публикует в Redis → `api/app/worker.py` обрабатывает.

### 3.2 Входящие от сервера (WsIncoming)

#### Основные события агента

| Тип | Когда | Payload |
|-----|-------|---------|
| `assistant_text` | Streaming текст от агента | `{ type, content }` |
| `tool_use` | Агент вызвал инструмент | `{ type, tool_name, tool_input }` |
| `tool_result` | Результат инструмента | `{ type, content }` |
| `done` | Агент завершил ответ | `{ type }` |
| `error` | Ошибка | `{ type, error }` |

#### Handoff / HITL события

| Тип | Когда | Payload |
|-----|-------|---------|
| `approval_required` | Граф паузирован в gate_node, нужно одобрение | `{ type, from_agent, to_agent, task }` |
| `handoff_start` | Начало handoff к sub-agent (после approve) | `{ type, from_agent, to_agent, task }` |
| `handoff_done` | Sub-agent завершил работу | `{ type, agent_name }` |
| `handoff_cycle_detected` | Обнаружен цикл handoff (A→B→A) | `{ type, message }` |

#### Sub-agent события

| Тип | Когда | Payload |
|-----|-------|---------|
| `sub_agent_assistant_text` | Streaming от sub-agent | `{ type, content, agent_name }` |
| `sub_agent_tool_use` | Sub-agent вызвал инструмент | `{ type, tool_name, tool_input, agent_name }` |
| `sub_agent_tool_result` | Результат инструмента sub-agent | `{ type, content, agent_name }` |
| `sub_agent_error` | Ошибка sub-agent | `{ type, error, agent_name }` |

#### Budget события (не в WsIncoming типе на frontend)

| Тип | Источник | Payload | Frontend |
|-----|----------|---------|----------|
| `budget_warning` | budget.py → runtime → graph_service | `{ type, level, spent_usd, limit_usd, usage_percent }` | Игнорируется |
| `budget_exceeded` | budget.py → runtime → graph_service | `{ type, level, spent_usd, limit_usd, call_count }` | Игнорируется |
| `sub_agent_budget_warning` | То же, с prefix для depth > 0 | То же + `agent_name` | Игнорируется |
| `sub_agent_budget_exceeded` | То же, с prefix для depth > 0 | То же + `agent_name` | Игнорируется |

Типы определены: `web/src/types/index.ts` (`WsIncoming`), обработка: `web/src/hooks/chat/chatEventHandler.ts` (`handleEvent`).

### 3.3 State machine (worker.py)

State machine переместилась из ws.py в worker.py (_run_session). ws.py — тонкий прокси.

```
                    ┌──────────────────────────────────┐
                    │       interrupted = false         │
                    │       (нормальный режим)          │
                    └──────┬──────────┬────────────────┘
                           │          │
                  "message" │          │ "stop"
                  (Redis)   │          │ (Redis)
                           ▼          ▼
              save to DB          stop runtime
              build WorkflowState  publish "done"
              _run_graph(state)    break (end session)
                     │
                     ├─ graph завершён (return false)
                     │  → publish "done" → Redis → ws.py → Client
                     │  → остаёмся в interrupted=false
                     │
                     └─ graph interrupted (return true)
                        → переход в interrupted=true
                           │
                    ┌──────▼──────────────────────────┐
                    │       interrupted = true          │
                    │       (ждёт approve/reject)       │
                    └──────┬──────────┬───────┬────────┘
                           │          │       │
                 "approve"  │ "reject" │       │ "message"
                 (Redis)    │ (Redis)  │       │ (Redis)
                           ▼          ▼       ▼
              _run_graph(       _run_graph(    publish error:
               Command(          Command(      "waiting for
               resume=True))     resume=False)) approval"
```

**Ключевые точки:**
- `interrupted` — единственный boolean флаг, управляющий состоянием сессии в Worker
- Команды приходят через Redis (subscribe_commands), не напрямую через WS
- WS disconnect НЕ влияет на Worker — граф продолжает работать
- Events публикуются через EventPublisher → Redis → ws.py → Client
- Cleanup (try/finally): stop children → stop runtime → clear buffer

### 3.4 Reconnection strategy (frontend + backend)

Реализована в `web/src/hooks/chat/useChatSocket.ts` (константы в `chatState.ts`):

| Параметр | Значение |
|----------|----------|
| `RECONNECT_BASE_DELAY_MS` | 1000 мс (начальная задержка) |
| `MAX_RECONNECT_ATTEMPTS` | 20 попыток |
| Стратегия | Exponential backoff: `base × 2^(attempt-1)`, cap 30s |
| Сброс счётчика | При успешном `onopen` (`reconnectCount = 0`) |
| Отмена reconnect | При вызове `stopAgent()` или cleanup effect |

**Поведение при disconnect:**
1. `ws.onclose` → статус `disconnected`
2. Сброс streaming-состояния (pendingText, pendingTools, pendingSubAgent)
3. Удаление `__streaming__` и `__sub_agent_streaming__` элементов из items
4. Если `reconnectCount < MAX_RECONNECT_ATTEMPTS` → setTimeout с exponential backoff → повторное подключение
5. После 20 неудачных попыток — остаёмся в `disconnected`

**Backend resilience (event buffer):**
- Worker продолжает работу при WS disconnect (публикует events в Redis)
- Events буферизуются в Redis list: `session:{id}:buffer` (max 500 events, TTL 1h)
- При reconnect ws.py: subscribe to pub/sub FIRST → replay buffer → forward live events
- Race condition решён: подписка на pub/sub ДО чтения буфера (нет зазора для потери событий)

---

## 4. LangGraph Workflow

### 4.1 Граф

```
START → run_agent ──→ [route_after_agent] ──→ END
                           │
                    HandoffResult?
                           │
              ┌────────────┼────────────┬──────────────┐
              │            │            │              │
        AWAITING_APPROVAL  FORWARDED   COMPLETED     BLOCKED
              │            │            │              │
              ▼            ▼            ▼              ▼
       notify_handoff  auto_handoff  complete_node  blocked_node
              │            │            │              │
              ▼            │            ▼              ▼
           gate ──→ [route │          END            END
                  _after   │     (task_completed)  (max_cycles
                  _gate]   │                        _reached)
                    │      │
             approved?     │
                    │ yes  │
                    ▼      ▼
              run_agent (цикл)
```

Файл: `api/app/services/graph_service.py` (~501 строк). Компилируется в `main.py` lifespan и `worker.py` run_worker() → `build_graph(checkpointer)`.

**Лимиты:**
- `MAX_DEPTH = 5` (graph_service.py) — макс. глубина sub-agent handoff
- `max_cycles` (per agent, per task) — из WorkflowEdge/Agent model, проверяется handoff_server
- `recursion_limit = 20` (worker.py) — LangGraph recursion limit в graph_config

### 4.2 Nodes

| Node | Функция | Что делает |
|------|---------|------------|
| `run_agent` | `run_agent_node()` | Стримит события из `runtime.send_message()` через EventPublisher (→ Redis → WS). Сохраняет ответ в DB. Парсит `\`\`\`handoff {...}\`\`\`` JSON-блок через `parse_handoff_from_text()` → `handle_handoff_tool_call()` → `HandoffResult`. Для sub-агентов (depth>0): добавляет prefix `sub_agent_` к событиям, останавливает runtime после завершения. |
| `notify_handoff` | `notify_handoff_node()` | Отправляет `approval_required` через EventPublisher + `broadcast_notification()` (Redis). Выполняется один раз — при resume графа не повторяется. |
| `gate` | `gate_node()` | Вызывает `interrupt()` — граф паузируется, state сохраняется в checkpoint. При resume с `Command(resume=True)`: создаёт sub-сессию, генерирует handoff tools для sub-agent, запускает runtime, отправляет `handoff_start`. При `Command(resume=False)`: отменяет handoff. |
| `auto_handoff` | `auto_handoff_node()` | Автоматический handoff (requires_approval=false). Создаёт sub-сессию и сразу переходит к run_agent без interrupt. |
| `complete` | `complete_node()` | Агент вызвал `complete_task` tool. Broadcast `task_completed` notification. → END. |
| `blocked` | `blocked_node()` | max_cycles exceeded. Broadcast `max_cycles_reached` notification. → END. |

### 4.3 Routing

| Функция | Входное условие | → Результат |
|---------|-----------------|-------------|
| `route_after_agent` | `handoff_result.type == AWAITING_APPROVAL` | → `notify_handoff` |
| `route_after_agent` | `handoff_result.type == FORWARDED` | → `auto_handoff` |
| `route_after_agent` | `handoff_result.type == COMPLETED` | → `complete` |
| `route_after_agent` | `handoff_result.type == BLOCKED` | → `blocked` |
| `route_after_agent` | no handoff | → `END` |
| `route_after_gate` | `gateway_approved == True` | → `run_agent` |
| `route_after_gate` | иначе | → `END` |

### 4.4 WorkflowState — поля и контракты

| Поле | Тип | Кто пишет | Кто читает | Описание |
|------|-----|-----------|------------|----------|
| `main_session_id` | str | worker.py (init) | run_agent, gate, auto_handoff | WebSocket-сессия (неизменна) |
| `current_session_id` | str | worker.py (init), gate, auto_handoff | run_agent | Claude SDK сессия текущего агента |
| `current_agent_id` | str | worker.py (init), gate, auto_handoff | gate | UUID текущего агента |
| `current_agent_name` | str | worker.py (init), gate, auto_handoff | run_agent, notify_handoff | Имя агента для UI |
| `workflow_id` | str\|None | worker.py (init) | run_agent, gate, auto_handoff | ID текущего workflow |
| `task_id` | str\|None | worker.py (init) | run_agent, gate, auto_handoff | ID текущей задачи (для max_cycles) |
| `task` | str | worker.py (init), gate, auto_handoff | run_agent | Текст задачи/сообщения |
| `depth` | int | worker.py (init=0), gate/auto_handoff (+1) | run_agent, route_after_agent | 0=main, >0=sub-agent |
| `chain` | list | worker.py (init=[]), gate, auto_handoff | gate | Пары `[[from, to], ...]` для детекции циклов |
| `handoff_result` | HandoffResult\|None | run_agent | route_after_agent, notify_handoff, gate, auto_handoff | Результат MCP handoff tool call |
| `gateway_approved` | bool\|None | run_agent (None), gate | route_after_gate | Решение HITL gate |
| `product_workspace` | str\|None | worker.py (init) | gate, auto_handoff | cwd для SDK — пропагируется через все handoffs |
| `messages` | list | worker.py (init=[]), run_agent | — | Накопленные `{agent, text, tools}` |

### 4.5 Checkpoint Persistence

- **Backend:** `AsyncPostgresSaver` (LangGraph) — таблицы `langgraph_checkpoints`, `langgraph_writes`
- **Инициализация:** `main.py` lifespan + `worker.py` run_worker() → `checkpointer.setup()` → `build_graph(checkpointer)` → `_compiled_graph`
- **Thread ID:** `session_id` — каждая сессия имеет изолированную историю checkpoints
- **Когда сохраняется:** после каждого node (автоматически LangGraph)
- **interrupt():** сохраняет state в checkpoint, паузирует граф. Resume через `Command(resume=value)`
- **Детекция interrupt:** `_run_graph()` (worker.py) проверяет `"__interrupt__" in chunk` при `stream_mode="values"`
- **Non-serializable configurable:** `websocket` (EventPublisher), `db` и `task_id` передаются через `config["configurable"]` и НЕ персистируются в checkpoint — нужно передавать при каждом `astream()`
- **DB session:** одна `AsyncSession` (из `async_session()`) живёт весь Worker session handler и используется всеми nodes. `expire_on_commit=False` (database.py:6) предотвращает инвалидацию ORM-объектов после commit внутри nodes
- **"stop" non-preemptive:** цикл `subscribe_commands` в worker.py блокируется на `_run_graph()` — команда "stop" обрабатывается только после завершения текущего graph execution
- **Disconnect resilience:** WS disconnect НЕ останавливает Worker. Cleanup (try/finally): stop child sessions → stop runtime → clear Redis buffer
- **Singleton:** `_compiled_graph` — module-level, устанавливается в lifespan (API) и run_worker (Worker), доступ через `get_graph()`

---

## 5. Dependency Graph

### 5.1 Зависимости сервисов

```
main.py (lifespan)
  ├─→ redis_service.init_redis()       — Redis connection pool
  ├─→ graph_service.build_graph(checkpointer)
  ├─→ graph_service._compiled_graph (singleton)
  ├─→ system_agent_service.seed_system_agent() (idempotent)
  └─→ redis_service.close_redis()      — cleanup

worker.py (Task Worker — отдельный процесс)
  ├─→ redis_service.init_redis()       — собственный Redis pool
  ├─→ graph_service.build_graph()      — собственный _compiled_graph
  ├─→ event_bus.subscribe_commands()   — входящие команды
  ├─→ event_bus.publish_event()        — через EventPublisher
  ├─→ event_bus.clear_buffer()         — cleanup
  ├─→ runtime.start_session()          — запуск SDK config
  ├─→ runtime.stop_session()           — cleanup (disconnect SDK client)
  ├─→ runtime.get_children()           — cleanup child sessions
  ├─→ session_service                  — CRUD сессий, add_message
  ├─→ task_service                     — auto-update task status
  ├─→ handoff_server                   — generate_handoff_tools, format_handoff_tools_prompt
  └─→ notification_service             — broadcast task_error (через event_bus)

ws.py (WS thin proxy)
  ├─→ redis_service.get_redis()        — pub/sub подписка
  ├─→ event_bus.get_buffered_events()  — replay при reconnect
  ├─→ event_bus.publish_command()      — forward команд в Worker
  ├─→ session_service                  — валидация session exists
  └─→ (NO graph_service, NO runtime)   — только прокси

graph_service
  ├─→ runtime.send_message()           — Claude Agent SDK
  ├─→ runtime.start_session()          — sub-agent config
  ├─→ runtime.stop_session()           — sub-agent cleanup
  ├─→ handoff_server                   — parse_handoff_from_text, handle_handoff_tool_call, generate_handoff_tools
  ├─→ notification_service             — broadcast approval_required, task_completed, max_cycles_reached
  ├─→ session_service                  — create/get/stop session, add_message
  └─→ agent_link_service               — get_agent_handoff_targets (legacy fallback)

event_bus
  └─→ redis_service.get_redis()        — все операции через Redis

notification_service
  └─→ event_bus.publish_notification() — Redis pub/sub (не in-memory)

runtime (AgentRuntime — Claude Agent SDK)
  ├─→ claude_agent_sdk (ClaudeSDKClient) — typed Python API
  ├─→ budget (BudgetTracker)           — встроен в __init__
  ├─→ circuit_breaker (CircuitBreaker) — встроен в __init__
  ├─→ auth_service                     — ⚠ lazy import в send_message()
  └─→ telemetry                        — ⚠ lazy import в send_message()

handoff_server
  ├─→ workflow_edge_service            — ⚠ implicit via DB queries on WorkflowEdge
  ├─→ session_service                  — count_agent_visits (via Session queries)
  └─→ (DB models: Agent, WorkflowEdge, Task, Session)

workflow_service
  └─→ (DB models: Workflow, Agent, Team, Task)

workflow_edge_service
  └─→ (DB models: WorkflowEdge, Workflow, Agent)

task_service
  └─→ (DB models: Task — status machine validation)

eval_service
  └─→ judge_service                    — LLM-as-Judge

business_service
  └─→ (нет внешних зависимостей, только DB)

product_service
  └─→ database.async_session            — ⚠ прямой импорт в _do_clone() (background task)

memory_service
  └─→ Voyage AI (external)             — embeddings
```

### 5.2 Hidden Dependencies (lazy imports)

| Где | Что импортируется | Строка | Почему скрыто |
|-----|-------------------|--------|---------------|
| `runtime.send_message()` | `auth_service.get_current_access_token` | runtime/agent_runner.py | `from app.services.auth_service import ...` внутри метода |
| `runtime.send_message()` | `telemetry.get_langfuse` | runtime/agent_runner.py | `from app.services.telemetry import ...` внутри метода |
| `product_service._do_clone()` | `database.async_session` | product_service.py | `from app.database import async_session` внутри фоновой задачи |

Lazy imports в runtime нужны для избежания циклических зависимостей, но скрывают реальные зависимости от статического анализа.

### 5.3 Module-level Singletons

| Singleton | Файл | Mutable | Инициализация |
|-----------|------|---------|---------------|
| `runtime` | runtime/agent_runner.py | Да (_sessions, _budget, _breaker) | При импорте модуля |
| `_compiled_graph` | graph_service.py | Да | В main.py lifespan + worker.py run_worker() |
| `_redis` | redis_service.py | Да | В main.py lifespan + worker.py run_worker() |
| `_langfuse` | telemetry.py | Да | При импорте модуля (если `LANGFUSE_SECRET_KEY` установлен) |
| `_code_verifier` | auth_service.py | Да | При вызове login |
| `_oauth_state` | auth_service.py | Да | При вызове login |
| `settings` | config.py | Нет | При импорте |
| `engine` | database.py | Нет | При импорте |

6 из 8 singletons имеют mutable state. `runtime`, `_compiled_graph` и `_redis` — ключевые для работы приложения. `notification_broker` удалён (заменён на Redis pub/sub через event_bus).

---

## 6. How-to Guides

### 6.1 Как добавить новый CRUD ресурс

См. [CLAUDE.md → API-конвенции](CLAUDE.md) — 5 файлов: model → schema → service → router → main.py.

### 6.2 Как добавить новый тип WS-события

**6 файлов:**

1. **Backend — генерация события:**
   - `api/app/services/graph_service.py` или `api/app/worker.py` — добавить `await ws.send_json({"type": "new_event", ...})`
   - Если событие из node — в соответствующем node в graph_service
   - Если событие из Worker — в worker.py (через EventPublisher → Redis → ws.py → Client)

2. **Backend — sub-agent prefix (если нужен):**
   - `api/app/services/graph_service.py` `run_agent_node()` — добавить prefix `sub_agent_` для depth>0

3. **Frontend — тип:**
   - `web/src/types/index.ts` — добавить в `WsIncoming` union type и interface

4. **Frontend — обработка:**
   - `web/src/hooks/chat/chatEventHandler.ts` — добавить `case "new_event":` в `handleEvent` switch

5. **Frontend — отображение:**
   - `web/src/components/ChatWindow.tsx` или создать новый компонент — рендеринг события

6. **Тесты:**
   - `web/src/hooks/chat/chatEventHandler.test.ts` — unit-тест для нового case (изолированно, без React hooks)
   - `web/src/hooks/useChat.test.ts` — интеграционный тест через хук

### 6.3 Как добавить новый LangGraph node

**4 файла:**

1. **Node function** — `api/app/services/graph_service.py`:
   ```python
   async def new_node(state: WorkflowState, config: RunnableConfig) -> dict:
       # Получить websocket/db из config["configurable"]
       ws = config["configurable"]["websocket"]  # EventPublisher or WebSocket
       db: AsyncSession = config["configurable"]["db"]
       # ... логика ...
       return {"field": new_value}  # partial update WorkflowState
   ```

2. **Routing function** (если нужна) — `api/app/services/graph_service.py`:
   ```python
   def route_after_new_node(state: WorkflowState) -> Literal["next_node", "__end__"]:
       if state.get("some_condition"):
           return "next_node"
       return END
   ```

3. **Регистрация в графе** — `api/app/services/graph_service.py` → `build_graph()`:
   ```python
   graph.add_node("new_node", new_node)
   graph.add_edge("previous_node", "new_node")          # или
   graph.add_conditional_edges("previous_node", route_fn) # conditional
   ```

4. **Тест** — `api/tests/test_graph_service.py`

**Если node использует `interrupt()`** — дополнительно обновить command handling в `api/app/worker.py` для обработки нового типа resume.

**Если node генерирует новые WS-события** — дополнительно см. секцию 6.2.

### 6.4 Как добавить новую страницу frontend

**4 файла:**

1. **Page component** — `web/src/pages/NewPage.tsx`:
   ```tsx
   export function NewPage() {
     // hooks для данных
     return <div>...</div>
   }
   ```

2. **Route** — `web/src/App.tsx`:
   ```tsx
   <Route path="/new-page" element={<NewPage />} />
   ```

3. **Hook** (если нужны данные) — `web/src/hooks/useNewResource.ts`:
   ```tsx
   export function useNewResources() {
     return useQuery({ queryKey: ["new-resources"], queryFn: getNewResources })
   }
   ```

4. **API layer** (если новый endpoint) — `web/src/api/newResource.ts`:
   ```tsx
   export async function getNewResources(): Promise<NewResource[]> {
     const res = await client.get("/api/new-resources")
     return res.data
   }
   ```

**Конвенции:** именованные экспорты, PascalCase для компонентов, camelCase для утилит. См. [CLAUDE.md → Frontend конвенции](CLAUDE.md).

---

## 7. Cross-Layer Contracts

Правила синхронизации между backend, frontend и Redis. Нарушение любого контракта вызывает silent failures.

### 7.1 WS Event Contract (backend → frontend)

**Source of truth:** `web/src/types/index.ts` → `WsIncoming` union type.

При добавлении нового event type нужно обновить ВСЕ три слоя:

| Шаг | Файл | Что сделать |
|-----|-------|------------|
| 1 | `graph_service.py` или `worker.py` | Отправить event через `ws.send_json({"type": "new_event", ...})` |
| 2 | `web/src/types/index.ts` | Добавить в `WsIncoming` union: `\| { type: "new_event"; ... }` |
| 3 | `chatEventHandler.ts` | Добавить `case "new_event":` в switch (иначе — console.warn из default) |

Если шаг 2–3 пропущен: событие доходит до клиента, но игнорируется с console.warn.

### 7.2 WS Command Contract (frontend → backend)

**Source of truth:** `worker.py` → `_run_session()` command dispatch.

| Command | Handler | Условие |
|---------|---------|---------|
| `message` | `_run_session` → `_run_graph` | `not interrupted` |
| `approve` | `_run_session` → `_run_graph(Command(resume=True))` | `interrupted` |
| `reject` | `_run_session` → `_run_graph(Command(resume=False))` | `interrupted` |
| `stop` | `_run_session` → `runtime.stop_session` | всегда |

При добавлении нового command: обновить `worker.py` dispatch + `WsOutgoing` в `types/index.ts`.

### 7.3 Redis Channel Contract

| Канал | Формат | Publisher | Subscriber |
|-------|--------|-----------|------------|
| `session:{id}:events` | JSON `{type: string, ...}` | `worker.py` (через event_bus) | `ws.py` (forward → WS) |
| `session:{id}:commands` | JSON `{type: string, ...}` | `ws.py` (через event_bus) | `worker.py` (subscribe_commands) |
| `session:{id}:buffer` | Redis list, JSON strings | `event_bus.publish_event` (RPUSH) | `ws.py` (get_buffered_events) |
| `worker:sessions` | JSON `{action: "start", session_id: string}` | `ws.py` (_notify_worker_start) | `worker.py` (run_worker) |
| `notifications` | JSON `{type: string, ...}` | `worker.py` (через event_bus) | `notifications_ws.py` |

### 7.4 Pydantic ↔ TypeScript Contract

Backend schemas (`api/app/schemas/*.py`) и frontend types (`web/src/types/index.ts`) ДОЛЖНЫ совпадать по именам полей.

**Проверка:** `cd web && npm run build` — type errors покажут рассинхронизацию в API layer (`web/src/api/*.ts`).

**Ручная синхронизация:** нет автоматической генерации типов. При изменении Pydantic schema — вручную обновить TypeScript interface.
