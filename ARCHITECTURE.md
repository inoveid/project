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
│  │ EvalDashboard│   │ useBusinesses  │    │ eval.ts      │  │   │
│  │ BusinessList │   │ useProducts    │    │ businesses.ts│  │   │
│  │ BusinessPage │   │ useTasks       │    │ products.ts  │  │   │
│  │ TeamPage     │   │ useWorkflows   │    │ tasks.ts     │  │   │
│  │ LoginPage    │   │ useCanvasData  │    │ workflows.ts │  │   │
│  └──────────────┘   │ useCanvasMut.  │    └──────────────┘  │   │
│       │             │ useChat (пакет)│                      │   │
│       ▼             └────────────────┘                      │   │
│  Components (85+)                                           │   │
│  ┌──────────────┐                                           │   │
│  │ ChatWindow   │   canvas/sidepanel/                       │   │
│  │ HandoffBlock │   ├ AgentGeneralTab                       │   │
│  │ SubAgentBlock│   ├ AgentPromptsTab                       │   │
│  │ TaskCard     │   ├ AgentHandoffTab                       │   │
│  │ KanbanColumn │   ├ AgentSubAgentsTab ← NEW               │   │
│  │ AgentNode    │   ├ EdgePanel                             │   │
│  │ TeamGroupNode│   └ SidePanel (4 tabs)                    │   │
│  └──────────────┘                                           │   │
│                                                             │   │
│  Types: types/index.ts (55+ type declarations)              │   │
└─────────────────────────────────────────────────────────────┼───┘
                                                              │
                               HTTP REST + WebSocket ─────────┘
                                                              │
┌─────────────────────────────────────────────────────────────┼───┐
│                     Backend (FastAPI)                        │   │
│                                                             ▼   │
│  Routers (13)               Services (26+)                      │
│  ┌───────────────┐         ┌──────────────────────────────┐     │
│  │ teams.py      │────────→│ team_service                 │     │
│  │ agents.py     │────────→│ agent_service                │     │
│  │ sessions.py   │────────→│ session_service              │     │
│  │ workflows.py  │────────→│ workflow_service              │     │
│  │ wf_edges.py   │────────→│ workflow_edge_service         │     │
│  │ auth.py       │────────→│ auth_service / auth_user      │     │
│  │ memory.py     │────────→│ memory_service               │     │
│  │ evaluations.py│────────→│ eval_service → judge_service │     │
│  │ businesses.py │────────→│ business_service             │     │
│  │ products.py   │────────→│ product_service              │     │
│  │ tasks.py      │────────→│ task_service                 │     │
│  └───────────────┘         └──────────────────────────────┘     │
│                                                                  │
│  ┌───────────────┐         ┌──────────────────────────────┐     │
│  │ ws.py         │─Redis──→│ worker.py (Task Worker)      │     │
│  │  WS thin proxy│  LIST   │  EventPublisher → Redis      │     │
│  │  ↔ Redis      │         │  subscribe_commands(BLPOP)   │     │
│  │               │         │  peer handoff orchestration  │     │
│  │ notif_ws.py   │─Redis──→│                              │     │
│  │  /ws/notif.   │  pub/sub│ graph_service.py             │     │
│  └───────────────┘         │  Single-agent graph:         │     │
│                            │  ├─ run_agent (spawn loop)   │     │
│  ┌───────────────┐         │  ├─ notify_handoff           │     │
│  │ Redis 7       │         │  ├─ gate (HITL interrupt)    │     │
│  │ event_bus.py  │         │  ├─ auto_handoff → END       │     │
│  │  pub/sub +    │         │  ├─ complete → END           │     │
│  │  LIST (cmds)  │         │  └─ blocked → END            │     │
│  │  LIST (buffer)│         │                              │     │
│  │ redis_service │         │  sub_agent_service.py ← NEW  │     │
│  └───────────────┘         │  ├─ spawn_agent (template)   │     │
│                            │  ├─ spawn_custom (ad-hoc)    │     │
│                            │  ├─ parallel (Semaphore)     │     │
│                            │  └─ format results           │     │
│                            │                              │     │
│                            │  runtime (Claude Agent SDK)  │     │
│                            │  ├─ budget                   │     │
│                            │  ├─ circuit_breaker          │     │
│                            │  └─ telemetry                │     │
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
│  └──────────────────┘  └────────────────┘                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Agent Architecture (v2)

Два механизма взаимодействия агентов:

### 2.1 Peer Handoff (depth=0)

Агенты workflow (Developer → Reviewer → Developer) работают как равноправные пиры.
Каждый агент — отдельная сессия, свой WebSocket, свой runtime.

```
Worker                     Graph
  │                          │
  ├─ start session A ───────→│ run_agent → handoff_result → END
  │                          │
  ├─ _handle_peer_handoff()  │
  │  ├─ create/reuse session B
  │  ├─ publish "done" on A
  │  ├─ publish "start" for B
  │  │
  ├─ start session B ───────→│ run_agent → ... → END
  │                          │
```

**Ключевой принцип:** граф всегда обрабатывает ОДНОГО агента и завершается (END).
Worker управляет переходами между пирами.

**Файлы:** `worker.py` (`_handle_peer_handoff`), `graph_service.py`, `handoff_server.py`.

### 2.2 Sub-agents (depth > 0)

Агент может вызвать помощников — через шаблоны или ad-hoc.

```
run_agent_node (parent)
  │
  ├─ runtime.send_message() → parent streams response
  ├─ parse_spawn_requests() → найдены spawn-блоки
  │
  ├─ run_spawn_requests()  (asyncio.gather + Semaphore)
  │   ├─ spawn_sub_agent(template_A, task_1) ──→ runtime session → result_1
  │   ├─ spawn_sub_agent(template_B, task_2) ──→ runtime session → result_2
  │   └─ (параллельно, max_concurrent=N)
  │
  ├─ format_sub_agent_results() → "## Sub-agent Results\n..."
  ├─ runtime.send_message(parent, results) → parent continues
  │
  └─ (цикл до MAX_SPAWN_ROUNDS=3)
```

Два способа вызова:

**spawn_agent** — по шаблону (настраивается в UI):
```
\`\`\`spawn_agent
{"role": "researcher", "task": "Find OAuth examples in FastAPI"}
\`\`\`
```

**spawn_custom** — ad-hoc (агент решает сам):
```
\`\`\`spawn_custom
{"name": "security-auditor", "instructions": "You are a security expert...", "task": "Check for SQL injection", "tools": ["Bash", "Read"]}
\`\`\`
```

**Ограничения:**
- `MAX_SUB_AGENT_DEPTH = 3` — вложенность суб-агентов
- `MAX_SUB_AGENTS_PER_TURN = 5` — запросов за один ответ
- `MAX_SPAWN_ROUNDS = 3` — циклов spawn→result→continue
- `max_sub_agents` (agent.config) — параллельных слотов (default 3)

**Файлы:** `sub_agent_service.py`, `graph_service.py` (run_agent_node), `worker.py` (prompt injection).

---

## 3. Потоки данных

### 3.1 CRUD flow

```
Client HTTP → Router → Service (AsyncSession + Pydantic) → SQLAlchemy → PostgreSQL
```

### 3.2 Chat flow (основной)

```
┌─────────┐    WS     ┌──────────┐   Redis LIST    ┌──────────────┐
│  Client  │◄────────►│  ws.py   │◄───────────────►│  worker.py   │
│ (browser)│          │ (proxy)  │  cmds/events    │ (Task Worker)│
└─────────┘           └──────────┘                  └──────┬───────┘
                           │                               │
                      Redis buffer               ┌─────────▼────────┐
                      (replay on                 │  LangGraph        │
                       reconnect)                │  graph_service    │
                                                 │    ↓              │
                                                 │  run_agent_node   │
                                                 │    ├─ runtime     │
                                                 │    └─ sub_agents  │
                                                 └──────────────────┘
```

**Последовательность:**
1. Client → WS connect `/api/ws/sessions/{session_id}`
2. ws.py: accept → publish command to Redis LIST → subscribe to Redis events
3. Worker (handle_session):
   a. Load agent, resolve workdir (product.workspace_path)
   b. Inject handoff tools + sub-agent prompt into system_prompt
   c. Start runtime (Claude Agent SDK)
   d. Listen for commands (BLPOP from Redis LIST)
4. On "message" command:
   a. Build WorkflowState → `_run_graph()`
   b. `run_agent_node`: stream events via runtime → EventPublisher → Redis → ws.py → Client
   c. If spawn_agent/spawn_custom detected → run sub-agents in parallel → feed results back → parent continues
   d. If handoff detected → route to gate/auto_handoff → END
5. Worker checks result:
   - `gateway_approved + handoff_result` → `_handle_peer_handoff()` → create/start next session
   - `completed` → update task status → done
   - No handoff → publish "done"

**Ключевые свойства:**
- WS disconnect НЕ останавливает Worker
- Events буферизуются в Redis list (500 events, 1h TTL) для reconnection replay
- Commands: Redis LIST (RPUSH/BLPOP) — гарантирует доставку
- Events: Redis pub/sub — real-time для WS

### 3.3 Memory flow

```
Agent tool → POST /api/memory/search → memory_service
  → Voyage AI embeddings → pgvector cosine distance → results
```

### 3.4 Evaluation flow

```
POST /api/eval/runs → BackgroundTask
  → for each case: agent output → judge_service (Claude API) → EvalResult
  → update EvalRun stats
```

---

## 4. LangGraph Workflow

### 4.1 Граф (single-agent)

```
START → run_agent ──→ [route_after_agent]:
                           │
                    ┌──────┼──────────┬──────────┬────────┐
                    │      │          │          │        │
              AWAITING   FORWARDED  COMPLETED  BLOCKED  (none)
                    │      │          │          │        │
                    ▼      ▼          ▼          ▼        ▼
             notify_    auto_      complete   blocked    END
             handoff    handoff     _node      _node
                │         │          │          │
                ▼         ▼          ▼          ▼
              gate       END        END        END
                │
                ▼
               END ← Worker reads gateway_approved + handoff_result
```

**Важно:** граф всегда завершается END. Peer handoff происходит в Worker, не в графе.

### 4.2 Nodes

| Node | Что делает |
|------|------------|
| `run_agent` | Стримит события из runtime. Обрабатывает spawn_agent/spawn_custom (до 3 раундов). Парсит handoff из текста. |
| `notify_handoff` | Отправляет `approval_required` notification. |
| `gate` | `interrupt()` — пауза до approve/reject. Возвращает `gateway_approved`. |
| `auto_handoff` | Устанавливает `gateway_approved=True`, → END. |
| `complete` | Broadcast `task_completed`. |
| `blocked` | Broadcast `max_cycles_reached`. |

### 4.3 Routing

| Функция | Условие | Результат |
|---------|---------|-----------|
| `route_after_agent` | `AWAITING_APPROVAL` | → `notify_handoff` |
| | `FORWARDED` | → `auto_handoff` |
| | `COMPLETED` | → `complete` |
| | `BLOCKED` | → `blocked` |
| | no handoff | → END |
| `route_after_gate` | всегда | → END |

### 4.4 WorkflowState

| Поле | Тип | Описание |
|------|-----|----------|
| `main_session_id` | str | WS-сессия (неизменна) |
| `current_session_id` | str | Runtime-сессия текущего агента |
| `current_agent_id` | str | UUID агента |
| `current_agent_name` | str | Имя для UI |
| `workflow_id` | str\|None | ID workflow |
| `task_id` | str\|None | ID задачи |
| `task` | str | Текст сообщения |
| `depth` | int | 0=peer, >0=sub-agent |
| `chain` | list | Пары [from, to] для детекции циклов |
| `handoff_result` | dict\|None | Результат handoff tool call |
| `gateway_approved` | bool\|None | Решение HITL gate |
| `product_workspace` | str\|None | Рабочая директория проекта |
| `messages` | list | Накопленные {agent, text, tools} |

---

## 5. WebSocket Protocol

Endpoint: `WS /api/ws/sessions/{session_id}`

### 5.1 Client → Server (WsOutgoing)

| Тип | Payload |
|-----|---------|
| `message` | `{ type, content: string }` |
| `stop` | `{ type }` |
| `approve` | `{ type }` |
| `reject` | `{ type }` |

### 5.2 Server → Client (WsIncoming)

**Основные:**

| Тип | Payload |
|-----|---------|
| `assistant_text` | `{ type, content }` |
| `tool_use` | `{ type, tool_name, tool_input }` |
| `tool_result` | `{ type, content }` |
| `done` | `{ type }` |
| `error` | `{ type, error }` |
| `status` | `{ type, status }` |

**Handoff / HITL:**

| Тип | Payload |
|-----|---------|
| `approval_required` | `{ type, from_agent, to_agent, task, chain?, steps?, workflow_agents? }` |
| `handoff_start` | `{ type, from_agent, to_agent, task }` |
| `handoff_cycle_detected` | `{ type, message }` |

**Sub-agent:**

| Тип | Payload |
|-----|---------|
| `sub_agent_spawned` | `{ type, sub_session_id, role, name, task }` |
| `sub_agent_assistant_text` | `{ type, sub_session_id, sub_agent_name, sub_agent_role, content }` |
| `sub_agent_tool_use` | `{ type, sub_session_id, sub_agent_name, tool_name, tool_input }` |
| `sub_agent_tool_result` | `{ type, sub_session_id, sub_agent_name, content }` |
| `sub_agent_done` | `{ type, sub_session_id, role, name, output_preview }` |
| `sub_agent_error` | `{ type, sub_session_id, role, name, error }` |

### 5.3 Worker State Machine

```
                    ┌───────────────────────┐
                    │   interrupted = false  │
                    └───┬──────────┬────────┘
                "message"│          │"stop"
                        ▼          ▼
                  _run_graph()   stop + done + break
                        │
              ┌─────────┼──────────┐
              │         │          │
          interrupted  completed   peer handoff
              │         │          │
              ▼         ▼          ▼
        ┌─────────┐  "done"   _handle_peer_handoff()
        │ = true  │            → create next session
        └──┬──┬───┘            → publish "start"
  "approve"│  │"reject"
           ▼  ▼
      resume(T/F) → same flow
```

### 5.4 Reconnection

- Frontend: exponential backoff (1s → 30s), max 20 attempts
- Backend: events buffered in Redis list (500 events, 1h TTL)
- Subscribe to pub/sub BEFORE reading buffer → no event gap

---

## 6. Data Model

### ORM Models (16)

| Model | Key Fields |
|-------|------------|
| Team | name, description, project_scoped |
| Agent | name, role, system_prompt, allowed_tools, config, prompts, **sub_agent_templates** (JSONB), max_cycles, can_complete_task |
| Session | agent_id, task_id, status, claude_session_id, **parent_session_id**, **depth** |
| Message | session_id, role, content, tool_uses |
| Workflow | team_id, starting_agent_id, starting_prompt |
| WorkflowEdge | from/to_agent_id, condition, prompt_template, requires_approval, max_rounds |
| Task | title, description, product_id, team_id, workflow_id, status |
| Business | name, description |
| Product | business_id, name, workspace_path, git_url, status |
| OAuthToken | access_token, refresh_token, expires_at |
| EpisodicMemory / SemanticMemory | pgvector embeddings |
| EvalCase / EvalRun / EvalResult | evaluation system |
| User | email, hashed_password |

### Pydantic Schemas

Паттерн: `{Resource}Create`, `{Resource}Update`, `{Resource}Read`. Pydantic v2, `from_attributes=True`.

Новые:
- `SubAgentTemplate` — id, role, name, system_prompt, allowed_tools, max_budget_usd, description
- `AgentCreate/Update/Read` — включают `sub_agent_templates` field

---

## 7. Frontend Architecture

### Key Components

| Component | Назначение |
|-----------|------------|
| `AgentNode` | Canvas нод агента. Бейджи: Start, End, **N sub-agents** (purple) |
| `SidePanel` | 4 вкладки: General, Prompts, Handoff, **Sub-agents** |
| `AgentSubAgentsTab` | CRUD шаблонов суб-агентов + настройка max_sub_agents |
| `SubAgentBlock` | Rich-отображение суб-агента в чате (статус: →/✓/✗) |
| `HandoffBlock` | Отображение handoff, activity, sub-agent items |
| `TaskChatsTab` | Per-session WebSocket (каждая сессия = отдельный useChat) |

### Chat Event Handler

`chatEventHandler.ts` — switch по WsIncoming.type:

- `assistant_text` → streaming message (`__streaming__`)
- `tool_use/tool_result` → update message + activity indicator
- `done` → finalize message
- `sub_agent_spawned` → persistent item (`sub-spawn-{id}`, → status)
- `sub_agent_done` → update item (✓ status)
- `sub_agent_error` → update item (✗ status)
- `sub_agent_*_text/tool_use/tool_result` → activity indicator
- `handoff_start` → divider line (agent → agent)
- `approval_required` → approval UI

---

## 8. Handoff Server

`handoff_server.py` — генерация MCP tools из workflow edges.

| Функция | Назначение |
|---------|------------|
| `generate_handoff_tools()` | Создаёт tools из WorkflowEdge + complete_task |
| `format_handoff_tools_prompt()` | Форматирует tools как system prompt инструкции |
| `handle_handoff_tool_call()` | Валидирует tool, проверяет max_rounds, возвращает HandoffResult |
| `parse_handoff_from_text()` | Парсит ` ```handoff {...}``` ` блок из ответа агента |

HandoffResultType: FORWARDED, AWAITING_APPROVAL, BLOCKED, COMPLETED.

---

## 9. Sub-agent Service

`sub_agent_service.py` — управление суб-агентами.

| Функция | Назначение |
|---------|------------|
| `parse_spawn_requests()` | Парсит `spawn_agent` + `spawn_custom` блоки из текста |
| `find_template()` | Ищет шаблон по role (case-insensitive) |
| `format_spawn_tools_prompt()` | Генерирует system prompt с описанием доступных суб-агентов |
| `spawn_sub_agent()` | Создаёт runtime session, запускает, собирает output, cleanup |
| `run_spawn_requests()` | Параллельный запуск через asyncio.gather + Semaphore |
| `format_sub_agent_results()` | Форматирует результаты для feedback в parent agent |

---

## 10. Cross-Layer Contracts

### WS Event Contract

При добавлении нового event: обновить `graph_service.py`/`worker.py` → `types/index.ts` (WsIncoming) → `chatEventHandler.ts`.

### Redis Channel Contract

| Канал | Тип | Publisher | Subscriber |
|-------|-----|-----------|------------|
| `session:{id}:events` | pub/sub | worker.py | ws.py |
| `session:{id}:commands` | LIST (RPUSH/BLPOP) | ws.py | worker.py |
| `session:{id}:buffer` | LIST | event_bus | ws.py (replay) |
| `worker:sessions` | pub/sub | ws.py, worker.py | worker.py |
| `notifications` | pub/sub | worker.py | notifications_ws.py |

### Pydantic ↔ TypeScript

Ручная синхронизация. При изменении Pydantic schema → обновить TypeScript interface.
Проверка: `cd web && npm run build`.

---

## 11. How-to Guides

### Добавить новый CRUD ресурс
5 файлов: model → schema → service → router → main.py.

### Добавить новый WS-событие
3 файла: backend (graph_service/worker) → types/index.ts (WsIncoming) → chatEventHandler.ts.

### Добавить новый LangGraph node
1 файл: graph_service.py — node function + routing + registration в build_graph().
Если interrupt() — обновить worker.py command handling.

### Добавить шаблон суб-агента
UI: Agent → Sub-agents tab → Add template (role, name, system_prompt, tools, budget).
Backend: сохраняется в agent.sub_agent_templates (JSONB).
Worker автоматически инжектит prompt с описанием доступных суб-агентов.

---

## 12. Dependency Graph (ключевые)

```
worker.py
  ├─→ graph_service (LangGraph)
  │     ├─→ runtime (Claude Agent SDK)
  │     ├─→ sub_agent_service (spawn/run sub-agents)
  │     ├─→ handoff_server (parse/handle handoff)
  │     └─→ session_service
  ├─→ event_bus → redis_service
  ├─→ handoff_server (generate tools, format prompt)
  ├─→ sub_agent_service (format spawn prompt)
  ├─→ session_service, task_service
  └─→ runtime (start/stop sessions)

ws.py (thin proxy)
  ├─→ event_bus (publish commands, subscribe events)
  ├─→ redis_service
  └─→ session_service (validate)

runtime (AgentRuntime)
  ├─→ claude_agent_sdk (ClaudeSDKClient)
  ├─→ budget (BudgetTracker)
  ├─→ circuit_breaker
  ├─→ auth_service (lazy import)
  └─→ telemetry (lazy import)
```

### Singletons

| Singleton | Файл | Mutable |
|-----------|------|---------|
| `runtime` | runtime/agent_runner.py | Да |
| `_compiled_graph` | graph_service.py | Да |
| `_redis` | redis_service.py | Да |
| `settings` | config.py | Нет |

---

## 13. Migrations

| # | Описание |
|---|----------|
| 001 | Initial schema |
| 002 | OAuth tokens |
| 003 | Vector memory |
| 004 | Evaluation |
| 005 | Businesses, products, agent is_system |
| 006 | Tasks |
| 007 | Workflows (replace agent_links) |
| 008 | Agent can_complete_task |
| 009 | Edge max_rounds |
| 010 | Specs |
| 011 | Users |
| 012 | **sub_agent_templates** (agents), **parent_session_id + depth** (sessions) |
