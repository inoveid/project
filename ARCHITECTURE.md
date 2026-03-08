# ARCHITECTURE.md

Архитектурная карта проекта Agent Console. Источник истины — текущий код.
Конвенции, команды и структура каталогов — см. [CLAUDE.md](CLAUDE.md).

---

## 1. Карта модулей

```
┌──────────────────────────────────────────────────────────────────┐
│                     Frontend (React + Vite)                      │
│                                                                  │
│  Pages (4)           Hooks (8)             API Layer (8)         │
│  ┌──────────────┐   ┌────────────────┐    ┌──────────────┐      │
│  │ Dashboard    │──→│ useTeams       │──→ │ teams.ts     │──┐   │
│  │ TeamPage     │   │ useAgents      │    │ agents.ts    │  │   │
│  │ ChatPage     │   │ useSessions    │    │ sessions.ts  │  │   │
│  │ EvalDashboard│   │ useAuth        │    │ auth.ts      │  │   │
│  └──────────────┘   │ useAgentLinks  │    │ eval.ts      │  │   │
│       │             │ useWorkspaces  │    │ agentLinks.ts│  │   │
│       ▼             │ useEvaluations │    │ workspaces.ts│  │   │
│  Components (30+)   └────────────────┘    └──────────────┘  │   │
│  ┌──────────────┐   ┌────────────────┐                      │   │
│  │ ChatPanel    │──→│ useChat (374)  │──── WebSocket ───────┼─┐ │
│  │ ChatWindow   │   │  13 WS events  │                      │ │ │
│  │ HandoffBlock │   └────────────────┘                      │ │ │
│  │ SessionList  │                                           │ │ │
│  └──────────────┘                                           │ │ │
│                                                             │ │ │
│  Types: types/index.ts (250 строк, 28 interfaces)          │ │ │
└─────────────────────────────────────────────────────────────┼─┼─┘
                                                              │ │
                               HTTP REST ─────────────────────┘ │
                               WebSocket ───────────────────────┘
                                                              │ │
┌─────────────────────────────────────────────────────────────┼─┼─┐
│                     Backend (FastAPI)                        │ │ │
│                                                             ▼ ▼ │
│  Routers (9)                Services (14)                       │
│  ┌───────────────┐         ┌──────────────────────────────┐     │
│  │ teams.py      │────────→│ team_service                 │     │
│  │ agents.py     │────────→│ agent_service                │     │
│  │ sessions.py   │────────→│ session_service              │     │
│  │ agent_links.py│────────→│ agent_link_service           │     │
│  │ auth.py       │────────→│ auth_service                 │     │
│  │ memory.py     │────────→│ memory_service               │     │
│  │ evaluations.py│────────→│ eval_service → judge_service │     │
│  │ workspaces.py │         │                              │     │
│  └───────────────┘         └──────────────────────────────┘     │
│                                                                  │
│  ┌───────────────┐         ┌──────────────────────────────┐     │
│  │ ws.py         │────────→│ graph_service                │     │
│  │  WS handler   │         │  Nodes:                      │     │
│  │  interrupted   │         │  ├─ run_agent (→runtime)     │     │
│  │  state flag   │         │  ├─ notify_handoff           │     │
│  └───────────────┘         │  └─ gate (HITL interrupt)    │     │
│                            │  Routing:                    │     │
│                            │  ├─ route_after_agent        │     │
│                            │  └─ route_after_gate         │     │
│                            │                              │     │
│                            │  runtime                     │     │
│                            │  ├─ budget                   │     │
│                            │  ├─ circuit_breaker          │     │
│                            │  └─ telemetry                │     │
│                            │                              │     │
│                            │  orchestrator_service        │     │
│                            │  (handoff formatting/parsing)│     │
│                            └──────────────────────────────┘     │
│                                       │                         │
│  ┌──────────────────┐                 │                         │
│  │ Models (11 ORM)  │←── SQLAlchemy ──┘                         │
│  │ Schemas (Pydantic)│                                          │
│  └────────┬─────────┘                                           │
│           ▼                                                     │
│  ┌──────────────────┐  ┌────────────────┐                      │
│  │ PostgreSQL       │  │ LangGraph      │                      │
│  │ + pgvector       │  │ Checkpoints    │                      │
│  │ 11 таблиц        │  │ (PostgreSQL)   │                      │
│  └──────────────────┘  └────────────────┘                      │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────┐    ┌─────────────────────┐
│  MCP Server (автономный) │    │  External APIs      │
│  server.py               │    │  ├─ Claude CLI       │
│  tools/tasks.py          │    │  ├─ Claude API       │
│  tools/specs.py          │    │  │   (judge_service) │
│  ─── stdio ──→ Claude    │    │  ├─ Voyage AI        │
│             Code         │    │  │   (memory_service)│
└──────────────────────────┘    │  └─ Langfuse (opt)   │
                                └─────────────────────┘
```

### Таблица модулей

#### Backend — Services

| Модуль | Строк | Ответственность |
|--------|-------|-----------------|
| runtime.py | ~419 | CLI subprocess lifecycle, budget tracking, circuit breaker |
| eval_service.py | ~312 | EvalCase/EvalRun CRUD, batch execution, comparison |
| graph_service.py | ~307 | LangGraph StateGraph: 3 nodes, 2 routing functions, checkpoint |
| auth_service.py | ~209 | OAuth2 PKCE, token refresh |
| budget.py | ~208 | BudgetTracker, cost computation, warning/critical events |
| orchestrator_service.py | ~203 | format_handoff_instructions, parse_handoff_block, _build_agent_prompt |
| memory_service.py | ~199 | pgvector RAG, Voyage AI embeddings |
| judge_service.py | ~198 | LLM-as-Judge via Anthropic SDK |
| circuit_breaker.py | ~151 | CLOSED/OPEN/HALF_OPEN state machine |
| team_service.py | ~107 | Team CRUD |
| agent_link_service.py | ~104 | AgentLink CRUD + routing |
| agent_service.py | ~104 | Agent CRUD |
| session_service.py | ~95 | Session + Message CRUD |
| telemetry.py | ~25 | Langfuse init wrapper |

#### Backend — Routers

| Модуль | Endpoints | Особенности |
|--------|-----------|-------------|
| ws.py | 1 WS | LangGraph streaming, interrupted state machine |
| evaluations.py | 8 REST | Background task execution |
| memory.py | 3 REST | Inline Pydantic schemas |
| agents.py | 6 REST | /agents + /teams/{id}/agents |
| workspaces.py | 2 REST | Git clone/init |
| teams.py | 5 REST | Standard CRUD |
| agent_links.py | 3 REST | Team-scoped |
| sessions.py | 4 REST | Status lifecycle |
| auth.py | 4 REST | OAuth PKCE flow |

#### Backend — Models & Schemas

11 ORM-моделей: Team, Agent, AgentLink, Session, Message, OAuthToken, EpisodicMemory, SemanticMemory, EvalCase, EvalRun, EvalResult.

Pydantic-схемы: паттерн `{Resource}Create`, `{Resource}Update`, `{Resource}Read`. Pydantic v2, `from_attributes=True`.

#### Frontend

| Категория | Файлов | Ключевые |
|-----------|--------|----------|
| Pages | 4 | Dashboard, TeamPage, ChatPage, EvalDashboard |
| Hooks | 8 | useChat (374 строк), useEvaluations, useAgents и др. |
| Components | 30+ | ChatPanel, AgentForm, EvalRunDetail и др. |
| API Layer | 8 | client.ts + 7 resource modules |
| Types | 1 | 28 interfaces/types, 13+ WS event types |

#### MCP Server (автономный, stdio)

| Файл | Ответственность |
|------|-----------------|
| server.py | FastMCP registration, resources |
| tools/tasks.py | list_tasks, get_task, update_task_status |
| tools/specs.py | list_specs, get_spec |

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

```
1. Client → WS connect /api/ws/sessions/{session_id}
2. ws.py: accept → load session → load agent → get handoff_targets
3. ws.py: format_handoff_instructions → append to system_prompt
4. ws.py: runtime.start_session() (если не запущен)
     → запуск Claude CLI subprocess
5. Client sends {"type": "message", "content": "..."}
6. ws.py: add_message(db, user) → build WorkflowState → _run_graph()
7. graph.astream() → run_agent_node:
     a. runtime.send_message():
        → kill stale CLI process этой сессии (если есть)
        → write content to stdin
        → stream JSON events from stdout
        → record budget usage (может yield budget_warning/budget_exceeded)
        → yield events (assistant_text, tool_use, tool_result)
     b. websocket.send_json(event) для каждого yield
     c. save response to DB (add_message assistant)
     d. parse_handoff_block → check handoff
8. route_after_agent:
     → handoff? → notify_handoff_node → gate_node
     → no handoff? → END
9. notify_handoff_node:
     → websocket.send_json({"type": "approval_required", ...})
10. gate_node: interrupt() → checkpoint state → ждёт approve/reject
11. Client sends {"type": "approve"} или {"type": "reject"}
12. ws.py: _run_graph(Command(resume=True/False))
13. gate_node resumes:
     → approved: create sub-agent session → runtime.start_session → run_agent_node (depth+1)
     → rejected: END
14. run_agent_node (sub-agent): те же шаги 7a-d, события с prefix sub_agent_
15. route_after_agent: END (или новый handoff, depth limited by recursion_limit=20)
16. ws.py: send {"type": "done"}
```

**Файлы (8+):** ws.py, graph_service.py, runtime.py, orchestrator_service.py, auth_service.py, budget.py, circuit_breaker.py, session_service.py.

Change isolation: **низкая** — изменение любого из 8+ файлов может сломать chat.

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

Типы определены: `web/src/types/index.ts` (`WsOutgoing`), обработка: `api/app/routers/ws.py` (`_handle_messages`).

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

Типы определены: `web/src/types/index.ts` (`WsIncoming`), обработка: `web/src/hooks/useChat.ts` (`handleEvent`).

### 3.3 State machine (ws.py)

```
                    ┌──────────────────────────────────┐
                    │       interrupted = false         │
                    │       (нормальный режим)          │
                    └──────┬──────────┬────────────────┘
                           │          │
                  "message" │          │ "stop"
                           ▼          ▼
              save to DB          kill process
              build WorkflowState  send "done"
              _run_graph(state)    break (close WS)
                     │
                     ├─ graph завершён (return false)
                     │  → send "done"
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
                           ▼          ▼       ▼
              _run_graph(       _run_graph(    send error:
               Command(          Command(      "waiting for
               resume=True))     resume=False)) approval"
                     │                │
                     ├─ return false  ├─ return false
                     │  → send "done" │  → send "done"
                     │  → interrupted │  → interrupted
                     │    = false     │    = false
                     │                │
                     └─ return true   └─ (теоретически
                        → остаёмся       возможно, но
                        interrupted      маловероятно)
                        = true
```

**Ключевые точки:**
- `interrupted` — единственный boolean флаг, управляющий состоянием WS-соединения
- Паузируется через `interrupt()` в `gate_node` (LangGraph checkpoint)
- Возобновляется через `Command(resume=True/False)` от LangGraph
- `_run_graph()` возвращает `True` если граф паузирован, `False` если завершён

### 3.4 Reconnection strategy (frontend)

Реализована в `web/src/hooks/useChat.ts`:

| Параметр | Значение |
|----------|----------|
| `RECONNECT_DELAY_MS` | 2000 мс (фиксированная задержка) |
| `MAX_RECONNECT_ATTEMPTS` | 5 попыток |
| Стратегия | Фиксированная задержка (не exponential backoff) |
| Сброс счётчика | При успешном `onopen` (`reconnectCount = 0`) |
| Отмена reconnect | При вызове `stopAgent()` или cleanup effect |

**Поведение при disconnect:**
1. `ws.onclose` → статус `disconnected`
2. Сброс streaming-состояния (pendingText, pendingTools, pendingSubAgent)
3. Удаление `__streaming__` и `__sub_agent_streaming__` элементов из items
4. Если `reconnectCount < MAX_RECONNECT_ATTEMPTS` → setTimeout → повторное подключение
5. После 5 неудачных попыток — остаёмся в `disconnected`
