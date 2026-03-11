# DANGER_ZONES.md

Файлы с высоким blast radius. Изменение любого из них может сломать ключевые функции приложения.
Источник истины — текущий код. Конвенции и структура — см. [CLAUDE.md](CLAUDE.md).

---

## Сводная таблица

| Файл | Blast Radius | Что может сломаться |
|------|-------------|-------------------|
| `api/app/services/runtime/` (пакет) | **HIGH** | Весь chat flow, budget tracking, circuit breaker, telemetry |
| `api/app/services/graph_service.py` | **HIGH** | Orchestration, MCP handoff, HITL gate, auto-handoff, sub-agent lifecycle, notifications |
| `api/app/services/handoff_server.py` | **HIGH** | MCP tool generation, handoff routing, max_cycles enforcement, prompt rendering |
| `api/app/routers/ws.py` | **HIGH** | Все WebSocket клиенты, task status auto-update, workdir resolution, reconnect |
| `web/src/hooks/chat/` (пакет) | **HIGH** | Весь chat UI, streaming, handoff визуализация |
| `web/src/types/index.ts` | **MEDIUM** | Frontend type contracts (48 type declarations (44 interfaces + 4 type aliases), WsIncoming/WsOutgoing) |
| `api/app/main.py` (lifespan) | **MEDIUM** | Startup, graph init, seed_system_agent, router registration (13 routers) |
| `api/app/database.py` | **MEDIUM** | Все DB-зависимые модули (13+ импортеров: все routers, services) |
| `api/app/config.py` | **MEDIUM** | Все модули через `settings` singleton (13+ импортеров) |
| `api/app/services/workflow_service.py` | **MEDIUM** | Workflow CRUD, locking (active tasks), validation — Canvas и Task creation зависят |
| `api/app/services/product_service.py` (`_do_clone`) | **MEDIUM** | Фоновые clone-задачи: утечки задач, зависшие статусы, stale DB sessions |
| `api/app/services/task_service.py` | **MEDIUM** | Task status machine — invalid transitions ломают Kanban + ws.py auto-update |
| `web/src/hooks/useSystemAgent.ts` | **LOW** | GlobalChatWidget застрянет в неготовом состоянии (не крашится, просто не работает) |
| `api/app/services/notification_service.py` | **LOW** | Toast notifications не доставляются (не блокирует основной flow) |

### Состояние тестов для danger zones

| Тест-файл | Статус | Проблема |
|-----------|--------|----------|
| `test_ws.py` | Частично | 6 тестов WS-протокола работают (session mock включает task_id=None). Удалён `test_ws_message_streams_response` (патчил P3-функцию `_stream_response`) |
| `test_runtime.py` | Существует | — |
| `test_graph_service.py` | **НЕ СУЩЕСТВУЕТ** | 0 тестов для 6 nodes, routing, interrupt, MCP handoff integration |
| `test_handoff.py` | Существует | 15 тестов: parse_handoff_block, format_handoff_instructions, build_agent_prompt |
| `test_handoff_server.py` | **НЕ СУЩЕСТВУЕТ** | 0 тестов для generate_handoff_tools, handle_handoff_tool_call, max_cycles |
| `test_tasks.py` | Существует | 10 тестов: Task CRUD router endpoints |
| `test_task_service.py` | Существует | 6 тестов: status transitions, required fields validation |
| `test_workflow_service.py` | **НЕ ПРОВЕРЕНО** | Нужно проверить наличие тестов для workflow locking |
| `notificationEventHandler.test.ts` | Существует | Frontend notification handler тесты |
| `useWorkflowValidation.test.ts` | Существует | Canvas validation тесты |
| `useToast.test.tsx` | Существует | Toast hook тесты |

При изменении core-модулей (runtime, graph_service, handoff_server, ws) автоматической защиты практически нет.

---

## Детали по каждому файлу

### 1. `api/app/services/runtime/` (пакет, ~440 строк) — HIGH

**Что делает:** Управляет жизненным циклом Claude CLI subprocess, budget tracking, circuit breaker, telemetry (Langfuse).

**Структура пакета:**
```
runtime/
├── __init__.py          — re-export: AgentRuntime, runtime, AgentRuntimeError, TransientAgentError, RunningProcess
├── agent_runner.py      — AgentRuntime class, runtime singleton (~209 строк)
├── cli_builder.py       — build_command() — построение CLI-команды (~32 строки)
├── event_parser.py      — parse_event(), read_stream() — чистые функции (~135 строк)
└── process_manager.py   — RunningProcess dataclass, kill_process(), launch_process() (~55 строк)
```

**Ключевые классы/функции:**
- `AgentRuntime` — singleton (`runtime = AgentRuntime()` в `agent_runner.py`)
- `start_session()` — регистрация сессии (конфиг, workdir lock)
- `send_message()` — запуск CLI subprocess, streaming событий, budget/circuit breaker
- `read_stream()` — парсинг JSON-событий из stdout Claude CLI (чистая функция в `event_parser.py`)
- `parse_event()` — преобразование raw events в типизированные dict'ы (чистая функция в `event_parser.py`)
- `stop_session()` — рекурсивная остановка процессов (включая children)

**Связанные модули:**
- `graph_service.py` — вызывает `runtime.send_message()`, `start_session()`, `stop_session()`
- `ws.py` — вызывает `runtime.start_session()`, `is_running()`, `stop_session()`, `get_children()`
- `sessions.py` (router) — импортирует `runtime` singleton напрямую для session lifecycle
- `budget.py` — встроен через `self._budget` (BudgetTracker)
- `circuit_breaker.py` — встроен через `self._breaker` (CircuitBreaker)
- `auth_service.py` — lazy import в `send_message()`, скрыт от статического анализа
- `telemetry.py` — lazy import в `send_message()`, скрыт от статического анализа


**Что проверить после изменения:**
- [ ] Chat flow работает: отправка сообщения → streaming ответа → done
- [ ] Sub-agent handoff: approve → sub-agent стримит → handoff_done
- [ ] Budget tracking: предупреждения и лимиты срабатывают
- [ ] Circuit breaker: ошибки CLI → breaker открывается → fail-fast
- [ ] Workdir lock: две сессии с одинаковым workdir — ошибка
- [ ] Stop session: процесс убивается, children тоже
- [ ] Reconnect: после WS disconnect и reconnect — новый send_message работает

**Какие тесты запустить:**
```bash
cd api && pytest tests/test_runtime.py -v
cd api && pytest tests/test_ws.py -v
cd api && pytest tests/test_handoff.py -v
cd web && npm test -- --run useChat
```

---

### 2. `api/app/services/graph_service.py` (~501 строк) — HIGH

**Что делает:** LangGraph StateGraph с 6 nodes (run_agent, notify_handoff, gate, auto_handoff, complete, blocked), 2 routing functions, MCP handoff integration, checkpoint persistence. Управляет orchestration, HITL approve/reject, auto-transitions и notifications.

**Ключевые функции:**
- `run_agent_node()` — стримит CLI события в WebSocket, сохраняет в DB, парсит handoff через `parse_handoff_from_text()` → `handle_handoff_tool_call()` → `HandoffResult`
- `notify_handoff_node()` — отправляет `approval_required` в WebSocket + `broadcast_notification()`
- `gate_node()` — `interrupt()` для HITL, создание sub-session, генерация handoff tools для sub-agent
- `auto_handoff_node()` — автоматический handoff (requires_approval=false), без interrupt
- `complete_node()` — broadcast `task_completed` notification → END
- `blocked_node()` — broadcast `max_cycles_reached` notification → END
- `route_after_agent()` — routes по `HandoffResult.result_type`: AWAITING_APPROVAL/FORWARDED/COMPLETED/BLOCKED/END
- `route_after_gate()` — approved → run_agent, rejected → END
- `build_graph()` — компиляция графа с checkpointer
- `WorkflowState` — TypedDict с workflow_id, task_id, handoff_result

**Связанные модули:**
- `ws.py` — вызывает `get_graph()`, передаёт websocket/db/task_id через configurable
- `runtime/` — `send_message()`, `start_session()`, `stop_session()`
- `handoff_server.py` — `parse_handoff_from_text()`, `handle_handoff_tool_call()`, `generate_handoff_tools()` (ключевая зависимость)
- `notification_service.py` — `broadcast_notification()` (approval, complete, blocked)
- `session_service.py` — `create_session()`, `add_message()`, `get_session()`, `stop_session()`
- `agent_link_service.py` — `get_agent_handoff_targets()` (legacy fallback для System Agent)
- `main.py` — lifespan инициализирует `_compiled_graph`


**Что проверить после изменения:**
- [ ] Простой chat (без handoff): message → streaming → done
- [ ] MCP handoff flow: agent вызывает handoff tool → approval_required → approve → sub-agent → handoff_done → done
- [ ] Auto-handoff flow: requires_approval=false → auto transition без interrupt
- [ ] Reject flow: approval_required → reject → done
- [ ] Complete flow: agent вызывает complete_task → task_completed notification → END
- [ ] Max cycles: agent visits > max_cycles → BLOCKED → max_cycles_reached notification → END
- [ ] Cycle detection: repeated A→B→A transitions
- [ ] Depth limit: depth >= MAX_DEPTH(5) → END без handoff
- [ ] Sub-agent DB cleanup: sub-session закрывается в DB (status=stopped)
- [ ] Notifications: все broadcast events доставляются через notification_service
- [ ] Checkpoint persistence: interrupt → restart server → state сохранён

**Какие тесты запустить:**
```bash
# test_graph_service.py НЕ СУЩЕСТВУЕТ — ручная проверка обязательна
# test_handoff_server.py НЕ СУЩЕСТВУЕТ — ручная проверка обязательна
cd api && pytest tests/test_handoff.py -v
cd api && pytest tests/test_ws.py -v
```

---

### 3. `api/app/routers/ws.py` (~296 строк) — HIGH

**Что делает:** WebSocket endpoint `/api/ws/sessions/{session_id}`. Управляет подключением, state machine (interrupted flag), маршрутизацией WS-сообщений, LangGraph streaming. Генерирует MCP handoff tools из workflow edges. Автоматически обновляет статус связанной Task (awaiting_user/in_progress/error/done). Broadcasts task_error notifications.

**Ключевые функции:**
- `websocket_session()` — accept, load session/agent, resolve workdir (task.product.workspace_path → agent.config.workdir fallback), generate handoff tools (if task+workflow), start runtime, handle disconnect cleanup
- `_handle_messages()` — основной цикл: message/approve/reject/stop dispatch; task_id из graph_config["configurable"]; auto-update task status
- `_run_graph()` — `graph.astream()` wrapper, детекция interrupt через `"__interrupt__" in chunk`; извлекает websocket/db/task_id из config
- `_try_update_task_status()` — безопасное обновление статуса задачи: HTTPException → info log (ожидаемый skip), Exception → error log (баг)

**Связанные модули:**
- `graph_service.py` — `get_graph()`, `WorkflowState`
- `runtime/` — `start_session()`, `is_running()`, `stop_session()`, `get_children()`
- `handoff_server.py` — `generate_handoff_tools()`, `format_handoff_tools_prompt()`
- `notification_service.py` — `broadcast_notification("task_error", ...)`
- `session_service.py` — `get_session()`, `add_message()`, `stop_session()`
- `task_service.py` — `update_task_status()` (через `_try_update_task_status`)
- `utils/handoff.py` — `format_handoff_instructions()` (legacy, System Agent)
- `main.py` — router registration (`app.include_router`)

**Особенности:**
- `interrupted` — boolean in-memory flag. При WS disconnect и reconnect сбрасывается в `False`. Если граф был в interrupt (ждал approve/reject), это состояние **теряется** — пользователь не узнает, что граф паузирован
- `db: AsyncSession` — одна на весь WS lifecycle (может быть часы). Stale reads возможны после interrupt/resume
- **Workdir resolution:** task.product.workspace_path (primary) → agent.config.workdir (fallback). Если task без product — fallback
- **Handoff tools injection:** если session имеет task+workflow → генерирует tools из workflow edges → добавляет в system_prompt


**Что проверить после изменения:**
- [ ] WS connect: подключение к существующей сессии
- [ ] WS connect: ошибка для несуществующей сессии (4004)
- [ ] Message flow: send message → graph execution → done
- [ ] Approve/reject: interrupted=true → approve/reject → graph resume
- [ ] Stop: корректная остановка и cleanup
- [ ] Disconnect cleanup: child sessions закрываются в DB, runtime останавливается
- [ ] Invalid JSON: ошибка без crash
- [ ] Message while interrupted: ошибка "waiting for approval"

**Какие тесты запустить:**
```bash
cd api && pytest tests/test_ws.py -v
```

---

### 4. `web/src/hooks/chat/` (пакет, 5 файлов) — HIGH

**Что делает:** React hook для всего chat UI. Декомпозирован на 4 модуля с чёткими границами ответственности.

**Структура пакета:**
```
hooks/chat/
├── index.ts              — re-export useChat, ChatStatus, UseChatResult
├── useChat.ts (~105)     — публичный API хука, композиция модулей
├── useChatSocket.ts (~106) — WebSocket connection + reconnect, инкапсулирует lifecycle
├── chatEventHandler.ts (~190) — handleEvent switch (13 cases), pure function (без React hooks); makeHandoffItem() — приватная фабрика для handoff/approval_required
└── chatState.ts (~36)    — типы (ChatStatus, PendingRefs, UseChatResult), константы, makeLocalMessage
```
Backward-compatible re-export: `hooks/useChat.ts` → `hooks/chat/`

**Границы модулей:**
- `chatEventHandler` — не зависит от React hooks, тестируется изолированно с моковыми refs/callbacks
- `useChatSocket` — не знает о доменной логике (streaming IDs, handoff items). Принимает `onEvent` и `onDisconnect` callbacks, возвращает `{ send, stop, isOpen }`
- `useChat` — композиция: state + refs + event handler + socket. Владеет доменной cleanup-логикой в `onDisconnect`
- `chatState` — shared types и утилиты, без побочных эффектов

**Важно: порядок useEffect.** В `useChat.ts` initialization effect **должен** быть объявлен перед вызовом `useChatSocket`, иначе `initializedRef.current` будет `false` при первом connect.

**Связанные модули:**
- `types/index.ts` — `WsIncoming`, `WsOutgoing`, `ChatItem`, `HandoffItem`, `Message`, `ToolUse`
- `components/ChatPanel.tsx` — основной потребитель hook (импортирует из `hooks/useChat`)
- `components/GlobalChatWidget.tsx` → `MiniChatWindow.tsx` — второй потребитель (global widget)
- `components/ChatWindow.tsx` — рендерит `ChatItem[]`
- `components/HandoffBlock.tsx` — рендерит handoff items

**Известные проблемы:**
- Budget events (`budget_warning`, `budget_exceeded`) не обрабатываются в `handleEvent` и не определены в `WsIncoming` — игнорируются молча
- Reconnect не восстанавливает interrupted state серверной стороны


**Что проверить после изменения:**
- [ ] Текстовый streaming: символы появляются по мере получения
- [ ] Tool use/result: отображаются в streaming и в финальном сообщении
- [ ] Done: streaming item заменяется на финальный Message
- [ ] Handoff approval: UI показывает approval request, кнопки работают
- [ ] Sub-agent streaming: текст и tools sub-agent отображаются
- [ ] Handoff done: sub-agent streaming item заменяется финальным
- [ ] Reconnect: после disconnect — автоматический reconnect, streaming state сброшен
- [ ] Error: отображается пользователю
- [ ] Stop: агент останавливается

**Какие тесты запустить:**
```bash
cd web && npm test -- --run chatEventHandler  # 19 unit-тестов (изолированные, без React hooks)
cd web && npm test -- --run useChat            # 23 интеграционных теста (через хук)
cd web && npm test -- --run ChatPanel          # 6 тестов компонента
```

---

### 4.5 `web/src/hooks/useAuth.ts` — потребители

`useAuthStatus()` из `useAuth.ts` теперь используется двумя независимыми контекстами:
- Страницы авторизации (AuthPage и др.) — обычный вызов
- `GlobalChatWidget` — вызов с дефолтным `polling=false`. Если нужен polling для виджета, передать `useAuthStatus(true)`

Единый `queryKey: ["auth", "status"]` гарантирует что оба потребителя читают из одного кеша TanStack Query — дублирующихся запросов нет.

---

### 5. `web/src/types/index.ts` — MEDIUM

**Что делает:** Все TypeScript интерфейсы и type unions. 48 type declarations (44 interfaces + 4 type aliases), включая `WsIncoming` (13 event types), `WsOutgoing` (4 message types), `ChatItem`, `HandoffItem`, `Task`, `Workflow`, `WorkflowEdge`, canvas validation types.

**Связанные модули:**
- Импортируется **всеми** frontend-файлами: hooks, components, API layer
- `hooks/chat/chatEventHandler.ts` — `WsIncoming`, `ChatItem`, `Message`, `HandoffItem`, `ApprovalRequest`
- `hooks/chat/useChat.ts` — `ChatItem`, `Message`, `ToolUse`, `HandoffItem`
- `api/*.ts` — типы для REST API (Team, Agent, Session и др.)
- `components/*.tsx` — типы для props

**Контракт frontend ↔ backend:**
- `WsIncoming` (frontend) должен точно соответствовать событиям, отправляемым из `ws.py` и `graph_service.py` (backend)
- `WsOutgoing` (frontend) должен соответствовать обработчикам в `_handle_messages()` (ws.py)
- При рассинхронизации: события игнорируются молча (нет default case с ошибкой в handleEvent switch)


**Что проверить после изменения:**
- [ ] `npm run build` — нет type errors
- [ ] `npm run lint` — нет ошибок
- [ ] Все компоненты рендерятся корректно (ChatWindow, HandoffBlock, TeamPage и др.)
- [ ] WS events обрабатываются (проверить что `WsIncoming` union совпадает с backend)

**Какие тесты запустить:**
```bash
cd web && npm run build
cd web && npm test
cd web && npm run lint
```

---

### 6. `api/app/main.py` (~55 строк) — MEDIUM

**Что делает:** FastAPI app, lifespan (PostgreSQL checkpointer init, graph compilation, seed_system_agent), CORS middleware, router registration (13 роутеров).

**Ключевые части:**
- `lifespan()` — `AsyncPostgresSaver.from_conn_string()` → `checkpointer.setup()` → `build_graph(checkpointer)` → `_compiled_graph` → `seed_system_agent()` (создаёт System Agent если нет)
- Router registration — 13 `app.include_router()` с prefix и tags
- CORS middleware — `settings.cors_origins`

**Связанные модули:**
- `graph_service.py` — `_compiled_graph`, `build_graph()`
- `config.py` — `settings` (database_url, cors_origins)
- Все 13 роутеров: teams, agents, workflows, workflow_edges, agent_links, sessions, businesses, products, tasks, ws, notifications_ws, auth, memory, evaluations
- `system_agent_service.py` — `seed_system_agent()` в lifespan

**Известные проблемы:**
- Нет try/except/retry на `checkpointer.setup()` — если PostgreSQL недоступен при старте, приложение не стартует без retry


**Что проверить после изменения:**
- [ ] `uvicorn app.main:app` — приложение стартует без ошибок
- [ ] Все API endpoints доступны (проверить OpenAPI docs `/docs`)
- [ ] WebSocket endpoint работает
- [ ] CORS headers корректны
- [ ] Graph инициализирован (отправка сообщения через WS работает)

**Какие тесты запустить:**
```bash
cd api && pytest -v
cd api && uvicorn app.main:app --reload  # ручная проверка старта
```

---

### 7. `api/app/database.py` (12 строк) — MEDIUM

**Что делает:** SQLAlchemy async engine, session factory (`async_session`), FastAPI dependency (`get_db`).

**Критичная настройка:** `expire_on_commit=False` — ORM-объекты остаются доступны после commit. Изменение этого параметра сломает все nodes в graph_service, которые коммитят и продолжают читать ORM-объекты.

**Связанные модули:**
- Все 13 роутеров (через `Depends(get_db)`)
- `auth_service.py`, `eval_service.py`, `product_service._do_clone()`, `handoff_server.py` (через `async_session` или ORM queries)


**Что проверить после изменения:**
- [ ] Все API endpoints отвечают (любое изменение engine/session ломает всё)
- [ ] WebSocket handler получает рабочую db session
- [ ] Background tasks (evaluations) получают рабочую session

**Какие тесты запустить:**
```bash
cd api && pytest -v  # все тесты зависят от database setup
```

---


### 7.5 `web/src/api/client.ts` — экспортируемый BASE_URL

`client.ts` экспортирует `BASE_URL = "/api"`. Используется напрямую в `deleteBusiness()` (businesses.ts) для кастомной обработки 409. Если значение изменится — нужно проверить все прямые импортёры `BASE_URL`.

**Импортёры BASE_URL:** `api/businesses.ts` (1 файл на текущий момент).

### 8. `api/app/config.py` (30 строк) — MEDIUM

**Что делает:** Pydantic Settings с env-prefix `AC_`. Единственный `settings` singleton, импортируемый 13+ модулями.

**Связанные модули:**
- `database.py` — `settings.database_url`
- `runtime/` — `settings.workspace_path`, `settings.claude_cli_path`, budget/circuit breaker params
- `graph_service.py` — `settings.workspace_path`
- `main.py` — `settings.cors_origins`, `settings.database_url`
- `product_service.py` — `settings.workspace_path`, `settings.clone_timeout_seconds`
- `auth_service.py`, `memory_service.py`
- `mcp/tools/platform.py` — `settings.api_base_url` (MCP Server → API HTTP вызовы)


**Поля Settings (16 параметров, env-prefix `AC_`):**
`database_url`, `claude_cli_path`, `workspace_path`, `cors_origins`, `oauth_client_id`, `oauth_authorize_url`, `oauth_token_url`, `oauth_redirect_uri`, `oauth_scopes`, `voyage_api_key`, `cb_failure_threshold`, `cb_recovery_timeout`, `cb_failure_window`, `budget_session_limit_usd`, `clone_timeout_seconds`, `api_base_url`

**Что проверить после изменения:**
- [ ] Приложение стартует с текущими env-переменными
- [ ] Дефолтные значения корректны для dev-среды
- [ ] Изменённые параметры используются в ожидаемых местах

**Какие тесты запустить:**
```bash
cd api && pytest -v
```
---

### 9. `api/app/services/product_service.py` (`_do_clone`) — MEDIUM

**Что делает:** Fire-and-forget фоновая задача `_do_clone()`, запускаемая через `asyncio.create_task()` при вызове `POST /api/products/{id}/clone`. Открывает собственную DB-сессию из `async_session`, выполняет `git clone --depth 1`, обновляет `product.status` → `ready` | `error`.

**Ключевые функции:**
- `clone_product()` — устанавливает `status=cloning`, коммитит, возвращает ответ, запускает фоновую задачу
- `_do_clone()` — фоновая задача: открывает сессию, проверяет `git_url`, запускает subprocess, таймаут `clone_timeout_seconds`, обновляет статус

**Риски фоновой задачи:**
- **Задача теряется при shutdown:** если сервер перезапустить пока идёт клон, `status` зависнет в `"cloning"` навсегда — нет механизма восстановления при старте
- **Повторный вызов:** `clone_product()` отклоняет запросы с `status="cloning"` через 409, но при перезапуске сервера этот guard не сработает (status="cloning" в DB, задача не запущена)
- **Утечка subprocess:** если `asyncio.wait_for` сработает с TimeoutError, `proc.kill()` вызывается, но subprocess может оставить незакрытые файловые дескрипторы на диске

**Связанные модули:**
- `database.py` — `async_session` используется напрямую (не через `Depends(get_db)`)
- `config.py` — `settings.clone_timeout_seconds` (default: 300 сек)
- `routers/products.py` — вызывает `clone_product()`, возвращает `ProductRead` с `status="cloning"`

**Frontend polling:** `useProduct(id, polling=true)` в `ProductCard` автоматически опрашивает сервер каждые 2 сек пока `status === 'cloning'` и останавливается при смене статуса. Изменение имён полей `status`/`clone_error` в `ProductRead` сломает polling и UI.

**Что проверить после изменения:**
- [ ] POST /clone возвращает 200 с `status="cloning"` немедленно (не блокирует на время clone)
- [ ] После успешного clone: GET /products/{id} возвращает `status="ready"`
- [ ] После ошибки clone: `status="error"` и `clone_error` содержит stderr
- [ ] Таймаут: если clone висит > `AC_CLONE_TIMEOUT_SECONDS` → `status="error"`, `clone_error="Clone timed out"`
- [ ] 409 при попытке clone пока уже идёт клонирование
- [ ] При `status="error"` повторный clone очищает директорию и запускается заново
- [ ] `git_url=None` → 400 ещё до запуска фоновой задачи

**Какие тесты запустить:**
```bash
cd api && pytest tests/test_products.py -v
```

---

### 10. `api/app/services/handoff_server.py` (~359 строк) — HIGH

**Что делает:** MCP tool-based handoff система. Заменяет текстовый парсинг handoff-блоков на структурированные JSON tool calls. Генерирует инструменты из workflow edges, обрабатывает вызовы, проверяет max_cycles, рендерит промпты.

**Ключевые классы/функции:**
- `HandoffTool` — dataclass: tool definition (name, to_agent, requires_approval, prompt_template)
- `HandoffResultType` (Enum) — FORWARDED, AWAITING_APPROVAL, BLOCKED, COMPLETED
- `HandoffResult` — dataclass: результат обработки tool call
- `generate_handoff_tools(db, agent_id, workflow_id)` — создаёт MCP tools из исходящих WorkflowEdge + `complete_task` для терминальных агентов
- `handle_handoff_tool_call(db, tool_name, tool_args, tools, task_id, agent_id)` — валидирует tool, проверяет max_cycles, возвращает HandoffResult
- `parse_handoff_from_text(text)` — извлекает ` ```handoff {...}``` ` JSON-блок из текста агента
- `count_agent_visits(db, task_id, agent_id)` — считает визиты через Session count
- `render_prompt(template, task)` — подставляет `{{task_title}}`, `{{task_description}}`

**Связанные модули:**
- `graph_service.py` — основной потребитель: `parse_handoff_from_text()`, `handle_handoff_tool_call()`, `generate_handoff_tools()`
- `ws.py` — вызывает `generate_handoff_tools()` и `format_handoff_tools_prompt()` при WS connect
- DB models: `Agent`, `WorkflowEdge`, `Task`, `Session` (прямые ORM queries)

**Риски:**
- **max_cycles enforcement:** если max_cycles слишком низкий — workflow не завершится, task уйдёт в error
- **Tool naming collision:** если два edge имеют одинаковый snake_case condition — конфликт имён tools
- **Prompt template injection:** `render_prompt()` делает простую подстановку `{{}}` — если task содержит `{{`, результат непредсказуем

**Что проверить после изменения:**
- [ ] MCP tools генерируются из workflow edges корректно
- [ ] complete_task tool появляется для терминальных агентов (без исходящих edges)
- [ ] max_cycles блокирует переход при превышении
- [ ] requires_approval=true → AWAITING_APPROVAL, =false → FORWARDED
- [ ] Prompt template rendering подставляет task fields
- [ ] JSON parse из agent text (`parse_handoff_from_text`) корректен
- [ ] Backward compat: System Agent (без task_id) не ломается

**Какие тесты запустить:**
```bash
# test_handoff_server.py НЕ СУЩЕСТВУЕТ — ручная проверка обязательна
cd api && pytest tests/test_handoff.py -v  # legacy handoff utils тесты
```

---

### 11. `api/app/services/task_service.py` (~108 строк) — MEDIUM

**Что делает:** Task CRUD и status machine. Валидирует переходы между статусами и required fields для in_progress.

**Ключевые константы:**
- `VALID_TRANSITIONS`: backlog→[in_progress], in_progress→[awaiting_user,done,error], awaiting_user→[in_progress,error], done→[in_progress], error→[in_progress]
- `REQUIRED_FOR_IN_PROGRESS`: [title, description, product_id, team_id, workflow_id]

**Связанные модули:**
- `ws.py` — вызывает `update_task_status()` через `_try_update_task_status()` (auto-update на interrupt/approve/error)
- `routers/tasks.py` — CRUD endpoints + PATCH /status
- `Dashboard.tsx` — Kanban drag & drop вызывает status transitions
- `TaskCard.tsx` — кнопка "Start" → backlog→in_progress

**Риски:**
- **Изменение VALID_TRANSITIONS** ломает ws.py auto-update (HTTPException при invalid transition → info log skip)
- **Изменение REQUIRED_FOR_IN_PROGRESS** может заблокировать запуск задач из Dashboard

**Что проверить после изменения:**
- [ ] Все переходы из Kanban drag & drop работают
- [ ] ws.py auto-update: awaiting_user, in_progress, error — не бросают unhandled exceptions
- [ ] backlog→in_progress требует все required fields
- [ ] done→in_progress (retry) работает

**Какие тесты запустить:**
```bash
cd api && pytest tests/test_tasks.py tests/test_task_service.py -v
```

---

### 12. `api/app/services/workflow_service.py` (~183 строк) — MEDIUM

**Что делает:** Workflow CRUD, active tasks проверка, workflow locking, validation. Canvas и Task creation зависят от корректной работы.

**Ключевые функции:**
- `get_active_tasks(db, workflow_id)` — возвращает tasks со статусом in_progress/awaiting_user
- `get_locked_workflow_ids(db, workflow_ids)` — подмножество с активными задачами (для Canvas lock)
- `validate_workflow(db, workflow_id)` — проверяет starting_agent и наличие edges

**Связанные модули:**
- `routers/workflows.py` — CRUD + GET /active-tasks
- `CanvasPage.tsx` → `useWorkflowLock.ts` — читает active tasks для lock UI
- `useWorkflowValidation.ts` — canvas validation rules
- `CreateTaskModal.tsx` — выбирает workflow для задачи

**Риски:**
- **Unique constraint (team_id, name):** при переименовании workflow может конфликтовать
- **starting_agent_id ON DELETE RESTRICT:** нельзя удалить агента, который является starting agent
- **Locking:** UI-level protection, backend не блокирует mutations на locked workflows

**Что проверить после изменения:**
- [ ] Canvas показывает lock badge для workflows с активными задачами
- [ ] Workflow CRUD (create, update, delete) работает
- [ ] Delete блокируется если starting_agent имеет RESTRICT constraint
- [ ] Validation корректно определяет missing starting_prompt и unreachable agents

**Какие тесты запустить:**
```bash
cd api && pytest tests/ -k workflow -v
```

