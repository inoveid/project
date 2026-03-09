# ARCHITECTURE.md

Архитектурная карта проекта Agent Console. Источник истины — текущий код.
Конвенции, команды и структура каталогов — см. [CLAUDE.md](CLAUDE.md).

---

## 1. Карта модулей

```
┌──────────────────────────────────────────────────────────────────┐
│                     Frontend (React + Vite)                      │
│                                                                  │
│  Pages (6)           Hooks (10)            API Layer (9)         │
│  ┌──────────────┐   ┌────────────────┐    ┌──────────────┐      │
│  │ Dashboard    │──→│ useTeams       │──→ │ teams.ts     │──┐   │
│  │ TeamPage     │   │ useAgents      │    │ agents.ts    │  │   │
│  │ ChatPage     │   │ useSessions    │    │ sessions.ts  │  │   │
│  │ EvalDashboard│   │ useAuth        │    │ auth.ts      │  │   │
│  │ BusinessList │   │ useAgentLinks  │    │ eval.ts      │  │   │
│  │ BusinessPage │   │ useBusinesses  │    │ agentLinks.ts│  │   │
│  └──────────────┘   │ useProducts    │    │ businesses.ts│  │   │
│       │             │ useEvaluations │    │ products.ts  │  │   │
│       ▼             │ useSystemAgent │    └──────────────┘  │   │
│  Components (34+)   └────────────────┘                      │   │
│  ┌──────────────┐   ┌────────────────┐                      │   │
│  │ ChatPanel    │──→│ useChat (374)  │──── WebSocket ───────┼─┐ │
│  │ ChatWindow   │   │  13 WS events  │                      │ │ │
│  │ MiniChatWindow│  └────────────────┘                      │ │ │
│  │ HandoffBlock │                                           │ │ │
│  │ SessionList  │                                           │ │ │
│  └──────────────┘                                           │ │ │
│                                                             │ │ │
│  GlobalChatWidget + MiniChatWindow (fixed bottom-right)     │ │ │
│    └─ useSystemAgent (localStorage session) + useAuth         │ │ │
│                                                             │ │ │
│  Types: types/index.ts (~290 строк, 34 interfaces)         │ │ │
└─────────────────────────────────────────────────────────────┼─┼─┘
                                                              │ │
                               HTTP REST ─────────────────────┘ │
                               WebSocket ───────────────────────┘
                                                              │ │
┌─────────────────────────────────────────────────────────────┼─┼─┐
│                     Backend (FastAPI)                        │ │ │
│                                                             ▼ ▼ │
│  Routers (10)               Services (17)                       │
│  ┌───────────────┐         ┌──────────────────────────────┐     │
│  │ teams.py      │────────→│ team_service                 │     │
│  │ agents.py     │────────→│ agent_service                │     │
│  │ sessions.py   │────────→│ session_service              │     │
│  │ agent_links.py│────────→│ agent_link_service           │     │
│  │ auth.py       │────────→│ auth_service                 │     │
│  │ memory.py     │────────→│ memory_service               │     │
│  │ evaluations.py│────────→│ eval_service → judge_service │     │
│  │ businesses.py │────────→│ business_service             │     │
│  │ products.py   │────────→│ product_service              │     │
│  │               │         │ system_agent_service          │     │
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
│                            │  utils/handoff               │     │
│                            │  (handoff formatting/parsing)│     │
│                            └──────────────────────────────┘     │
│                                       │                         │
│  ┌──────────────────┐                 │                         │
│  │ Models (13 ORM)  │←── SQLAlchemy ──┘                         │
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
| runtime/ (пакет) | ~440 | CLI subprocess lifecycle, budget tracking, circuit breaker. 4 модуля: agent_runner, cli_builder, event_parser, process_manager |
| eval_service.py | ~312 | EvalCase/EvalRun CRUD, batch execution, comparison |
| graph_service.py | ~307 | LangGraph StateGraph: 3 nodes, 2 routing functions, checkpoint |
| auth_service.py | ~209 | OAuth2 PKCE, token refresh |
| budget.py | ~208 | BudgetTracker, cost computation, warning/critical events |
| utils/handoff.py | ~50 | format_handoff_instructions, parse_handoff_block, build_agent_prompt |
| memory_service.py | ~199 | pgvector RAG, Voyage AI embeddings |
| judge_service.py | ~198 | LLM-as-Judge via Anthropic SDK |
| circuit_breaker.py | ~151 | CLOSED/OPEN/HALF_OPEN state machine |
| team_service.py | ~107 | Team CRUD |
| agent_link_service.py | ~104 | AgentLink CRUD + routing |
| agent_service.py | ~104 | Agent CRUD |
| session_service.py | ~95 | Session + Message CRUD |
| business_service.py | ~90 | Business CRUD, force delete, scalar subquery products_count |
| product_service.py | ~110 | Product CRUD, async git clone (fire-and-forget), status lifecycle |
| system_agent_service.py | ~25 | System Agent seed (idempotent) |
| telemetry.py | ~25 | Langfuse init wrapper |

#### Backend — Routers

| Модуль | Endpoints | Особенности |
|--------|-----------|-------------|
| ws.py | 1 WS | LangGraph streaming, interrupted state machine |
| evaluations.py | 8 REST | Background task execution |
| memory.py | 3 REST | Inline Pydantic schemas |
| agents.py | 7 REST | /agents + /teams/{id}/agents + /agents/system |
| businesses.py | 5 REST | Business CRUD (force delete support) |
| products.py | 6 REST | Product CRUD + POST /clone (fire-and-forget) |
| teams.py | 5 REST | Standard CRUD |
| agent_links.py | 3 REST | Team-scoped |
| sessions.py | 4 REST | Status lifecycle |
| auth.py | 4 REST | OAuth PKCE flow |

#### Backend — Models & Schemas

13 ORM-моделей: Team, Agent (+ is_system, nullable team_id/role), AgentLink, Session, Message, OAuthToken, EpisodicMemory, SemanticMemory, EvalCase, EvalRun, EvalResult, Business, Product.

Pydantic-схемы: паттерн `{Resource}Create`, `{Resource}Update`, `{Resource}Read`. Pydantic v2, `from_attributes=True`.

#### Frontend

| Категория | Файлов | Ключевые |
|-----------|--------|----------|
| Pages | 6 | Dashboard, TeamPage, ChatPage, EvalDashboard, BusinessListPage, BusinessPage |
| Hooks | 10 | useChat (пакет `hooks/chat/`, 5 файлов), useAuth (auth + polling), useSystemAgent (system session), useBusinesses, useProducts, useEvaluations, useAgents и др. |
| Components | 34+ | ChatPanel, MiniChatWindow, AgentForm, EvalRunDetail, BusinessCard, ProductCard, GlobalChatWidget и др. |
| API Layer | 9 | client.ts (экспортирует BASE_URL) + 8 resource modules; `agents.ts` добавлен `getSystemAgent()` |
| Types | 1 | 34 interfaces/types, 13+ WS event types |

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
     → НЕ запускает subprocess — только сохраняет конфигурацию
       (workdir, system_prompt, claude_session_id, allowed_tools, budget)
5. Client sends {"type": "message", "content": "..."}
6. ws.py: add_message(db, user) → build WorkflowState → _run_graph()
7. graph.astream() → run_agent_node:
     a. runtime.send_message():
        → kill stale CLI process этой сессии (если есть)
        → get OAuth token (auth_service.get_current_access_token)
        → check budget (BudgetTracker)
        → check circuit_breaker
        → launch NEW Claude CLI subprocess (эфемерный — новый на каждое сообщение)
        → write content to stdin + EOF
        → stream JSON events from stdout (_read_stream)
        → record budget usage (может yield budget_warning/budget_exceeded)
        → yield events (assistant_text, tool_use, tool_result)
     b. websocket.send_json(event) для каждого yield
        — depth > 0: события получают prefix sub_agent_
     c. save response to DB (add_message assistant)
        — depth > 0: также сохраняет в main_session для истории
     d. parse_handoff_block → check handoff
     e. depth > 0: runtime.stop_session() (cleanup sub-agent)
        depth == 0: сохраняет claude_session_id для resume
8. route_after_agent:
     → handoff? → notify_handoff_node → gate_node
     → no handoff? → END
9. notify_handoff_node:
     → websocket.send_json({"type": "approval_required", ...})
10. gate_node: interrupt() → checkpoint state → ждёт approve/reject
11. Client sends {"type": "approve"} или {"type": "reject"}
12. ws.py: _run_graph(Command(resume=True/False))
13. gate_node resumes:
     → approved: check cycle → create sub-session → build_agent_prompt
       → runtime.start_session (config only) → send "handoff_start"
       → return state с depth+1 → run_agent_node (шаг 7)
     → rejected: END
14. route_after_agent: END (или новый handoff, depth limited by recursion_limit=20)
15. ws.py: send {"type": "done"}
```

**Файлы (8+):** ws.py, graph_service.py, runtime/ (пакет), utils/handoff.py, auth_service.py, budget.py, circuit_breaker.py, session_service.py.

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



### 2.6 GlobalChatWidget flow

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

Типы определены: `web/src/types/index.ts` (`WsIncoming`), обработка: `web/src/hooks/chat/chatEventHandler.ts` (`handleEvent`).

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

Реализована в `web/src/hooks/chat/useChatSocket.ts` (константы в `chatState.ts`):

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

---

## 4. LangGraph Workflow

### 4.1 Граф

```
START → run_agent ──→ [route_after_agent] ──→ END
                           │
                    handoff_target?
                    depth < MAX_DEPTH(5)?
                           │ yes
                           ▼
                    notify_handoff → gate ──→ [route_after_gate] ──→ END
                                                    │
                                             gateway_approved?
                                                    │ yes
                                                    ▼
                                              run_agent (цикл)
```

Файл: `api/app/services/graph_service.py`. Компилируется в `main.py` lifespan → `build_graph(checkpointer)`.

**Лимиты:**
- `MAX_DEPTH = 5` (graph_service.py:35) — макс. глубина sub-agent handoff
- `recursion_limit = 20` (ws.py:78) — LangGraph recursion limit в graph_config

### 4.2 Nodes

| Node | Функция | Что делает |
|------|---------|------------|
| `run_agent` | `run_agent_node()` | Стримит события из `runtime.send_message()` в WebSocket. Сохраняет ответ в DB. Парсит handoff-блок из ответа. Для sub-агентов (depth>0): добавляет prefix `sub_agent_` к событиям, останавливает runtime после завершения. |
| `notify_handoff` | `notify_handoff_node()` | Отправляет `approval_required` в WebSocket. Выполняется один раз — при resume графа не повторяется. |
| `gate` | `gate_node()` | Вызывает `interrupt()` — граф паузируется, state сохраняется в checkpoint. При resume с `Command(resume=True)`: создаёт sub-сессию, запускает runtime sub-агента, отправляет `handoff_start`. При `Command(resume=False)`: отменяет handoff. |

### 4.3 Routing

| Функция | Входное условие | → Результат |
|---------|-----------------|-------------|
| `route_after_agent` | `handoff_target` есть и `depth < MAX_DEPTH` | → `notify_handoff` |
| `route_after_agent` | иначе | → `END` |
| `route_after_gate` | `gateway_approved == True` | → `run_agent` |
| `route_after_gate` | иначе | → `END` |

### 4.4 WorkflowState — поля и контракты

| Поле | Тип | Кто пишет | Кто читает | Описание |
|------|-----|-----------|------------|----------|
| `main_session_id` | str | ws.py (init) | run_agent, gate | WebSocket-сессия (неизменна) |
| `current_session_id` | str | ws.py (init), gate | run_agent | Claude CLI сессия текущего агента |
| `current_agent_id` | str | ws.py (init), gate | gate | UUID текущего агента |
| `current_agent_name` | str | ws.py (init), gate | run_agent, notify_handoff | Имя агента для UI |
| `task` | str | ws.py (init), gate | run_agent | Текст задачи/сообщения |
| `depth` | int | ws.py (init=0), gate (+1) | run_agent, route_after_agent | 0=main, >0=sub-agent |
| `chain` | list | ws.py (init=[]), gate | gate | Пары `[[from, to], ...]` для детекции циклов |
| `handoff_target` | str\|None | run_agent | route_after_agent, notify_handoff, gate | Имя целевого агента из handoff-блока |
| `handoff_message` | str\|None | run_agent | notify_handoff, gate | Текст задачи для sub-агента |
| `gateway_approved` | bool\|None | run_agent (None), gate | route_after_gate | Решение HITL gate |
| `messages` | list | ws.py (init=[]), run_agent | — | Накопленные `{agent, text, tools}` |

### 4.5 Checkpoint Persistence

- **Backend:** `AsyncPostgresSaver` (LangGraph) — таблицы `langgraph_checkpoints`, `langgraph_writes`
- **Инициализация:** `main.py` lifespan → `checkpointer.setup()` → `build_graph(checkpointer)` → `_compiled_graph`
- **Thread ID:** `session_id` — каждая WS-сессия имеет изолированную историю checkpoints
- **Когда сохраняется:** после каждого node (автоматически LangGraph)
- **interrupt():** сохраняет state в checkpoint, паузирует граф. Resume через `Command(resume=value)`
- **Детекция interrupt:** `_run_graph()` (ws.py:191) проверяет `"__interrupt__" in chunk` при `stream_mode="values"`
- **Non-serializable configurable:** `websocket` и `db` передаются через `config["configurable"]` и НЕ персистируются в checkpoint — нужно передавать при каждом `astream()`
- **DB session:** одна `AsyncSession` (из `Depends(get_db)`) живёт весь WS connection и используется всеми nodes. `expire_on_commit=False` (database.py:6) предотвращает инвалидацию ORM-объектов после commit внутри nodes
- **"stop" non-preemptive:** цикл `_handle_messages` блокируется на `_run_graph()` — команда "stop" обрабатывается только после завершения текущего graph execution
- **Disconnect cleanup:** при `WebSocketDisconnect` ws.py сначала закрывает orphaned child sessions в DB (`stop_session(db, child_id)` для каждого `runtime.get_children()`), затем вызывает `runtime.stop_session(session_id)`
- **Singleton:** `_compiled_graph` — module-level, устанавливается в lifespan, доступ через `get_graph()`

---

## 5. Dependency Graph

### 5.1 Зависимости сервисов

```
main.py (lifespan)
  ├─→ graph_service.build_graph(checkpointer)
  ├─→ graph_service._compiled_graph (singleton)
  └─→ system_agent_service.seed_system_agent() (idempotent)

ws.py (WebSocket handler)
  ├─→ graph_service.get_graph()        — скомпилированный граф
  ├─→ runtime.start_session()          — запуск CLI config
  ├─→ runtime.is_running()             — проверка перед start
  ├─→ runtime.get_children()           — orphaned children при disconnect
  ├─→ runtime.stop_session()           — cleanup
  ├─→ session_service                  — CRUD сессий
  ├─→ agent_link_service               — handoff targets
  └─→ utils/handoff                     — format_handoff_instructions

graph_service
  ├─→ runtime.send_message()           — CLI subprocess
  ├─→ runtime.start_session()          — sub-agent config
  ├─→ runtime.stop_session()           — sub-agent cleanup
  ├─→ utils/handoff                    — parse_handoff_block, build_agent_prompt
  ├─→ session_service                  — create/get/stop session, add_message
  └─→ agent_link_service               — get_agent_handoff_targets

runtime (AgentRuntime)
  ├─→ budget (BudgetTracker)           — встроен в __init__
  ├─→ circuit_breaker (CircuitBreaker) — встроен в __init__
  ├─→ auth_service                     — ⚠ lazy import в send_message()
  └─→ telemetry                        — ⚠ lazy import в send_message()

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
| `runtime` | runtime/agent_runner.py | Да (_processes, _budget, _breaker) | При импорте модуля |
| `_compiled_graph` | graph_service.py:301 | Да | В main.py lifespan |
| `_langfuse` | telemetry.py:12 | Да | При импорте модуля (если `LANGFUSE_SECRET_KEY` установлен) |
| `_code_verifier` | auth_service.py:21 | Да | При вызове login |
| `_oauth_state` | auth_service.py:22 | Да | При вызове login |
| `settings` | config.py:29 | Нет | При импорте |
| `engine` | database.py:5 | Нет | При импорте |

5 из 7 singletons имеют mutable state. `runtime` и `_compiled_graph` — ключевые для работы приложения.

---

## 6. How-to Guides

### 6.1 Как добавить новый CRUD ресурс

См. [CLAUDE.md → API-конвенции](CLAUDE.md) — 5 файлов: model → schema → service → router → main.py.

### 6.2 Как добавить новый тип WS-события

**6 файлов:**

1. **Backend — генерация события:**
   - `api/app/services/graph_service.py` или `api/app/routers/ws.py` — добавить `await ws.send_json({"type": "new_event", ...})`
   - Если событие из node — в соответствующем node в graph_service
   - Если событие из WS handler — в ws.py

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
       ws: WebSocket = config["configurable"]["websocket"]
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

**Если node использует `interrupt()`** — дополнительно обновить `_handle_messages` в `api/app/routers/ws.py` для обработки нового типа resume.

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
