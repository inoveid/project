# DANGER_ZONES.md

Файлы с высоким blast radius. Изменение любого из них может сломать ключевые функции приложения.
Источник истины — текущий код. Конвенции и структура — см. [CLAUDE.md](CLAUDE.md).

---

## Сводная таблица

| Файл | Blast Radius | Что может сломаться |
|------|-------------|-------------------|
| `api/app/worker.py` | **CRITICAL** | Весь chat flow — Worker единственный процесс, выполняющий LangGraph |
| `api/app/services/event_bus.py` | **CRITICAL** | Redis pub/sub каналы, event buffer — весь realtime transport |
| `api/app/services/redis_service.py` | **HIGH** | Redis connection pool — от него зависят event_bus, worker, ws |
| `api/app/services/runtime/` (пакет) | **HIGH** | Agent SDK lifecycle, budget tracking, circuit breaker, telemetry |
| `api/app/services/graph_service.py` | **HIGH** | Orchestration, MCP handoff, HITL gate, auto-handoff, sub-agent lifecycle |
| `api/app/services/handoff_server.py` | **HIGH** | MCP tool generation, handoff routing, max_cycles enforcement, prompt rendering |
| `api/app/routers/ws.py` | **HIGH** | WebSocket thin proxy — ретранслирует Redis ↔ WS, replay buffer |
| `web/src/hooks/chat/` (пакет) | **HIGH** | Весь chat UI, streaming, handoff визуализация, reconnect с backoff |
| `web/src/types/index.ts` | **MEDIUM** | Frontend type contracts (48 type declarations, WsIncoming/WsOutgoing) |
| `api/app/main.py` (lifespan) | **MEDIUM** | Startup, Redis init, graph init, seed_system_agent, router registration |
| `api/app/database.py` | **MEDIUM** | Все DB-зависимые модули (13+ импортеров: все routers, services) |
| `api/app/config.py` | **MEDIUM** | Все модули через `settings` singleton (13+ импортеров) |
| `api/app/services/workflow_service.py` | **MEDIUM** | Workflow CRUD, locking (active tasks), validation — Canvas и Task creation зависят |
| `api/app/services/product_service.py` (`_do_clone`) | **MEDIUM** | Фоновые clone-задачи: утечки задач, зависшие статусы, stale DB sessions |
| `api/app/services/task_service.py` | **MEDIUM** | Task status machine — invalid transitions ломают Kanban + worker auto-update |
| `web/src/hooks/useSystemAgent.ts` | **LOW** | GlobalChatWidget застрянет в неготовом состоянии (не крашится, просто не работает) |
| `api/app/services/notification_service.py` | **LOW** | Toast notifications — тонкий wrapper над event_bus.publish_notification |

### Состояние тестов для danger zones

| Тест-файл | Статус | Покрытие |
|-----------|--------|----------|
| `test_ws.py` | ✅ Переписан | 7 тестов: proxy session validation, buffer replay, Redis event forwarding, command publishing, stop, invalid JSON |
| `test_runtime.py` | ✅ Переписан | 9 тестов: AgentSession lifecycle (start/stop/workdir/duplicates/children/stale) — SDK-based |
| `test_notification_service.py` | ✅ Переписан | 3 теста: broadcast_notification → Redis pub/sub wrapper |
| `test_notifications_ws.py` | ✅ Переписан | 2 теста: notifications WS accept + event forwarding |
| `test_graph_service.py` | **НЕ СУЩЕСТВУЕТ** | 0 тестов для 6 nodes, routing, interrupt, MCP handoff integration |
| `test_handoff.py` | Существует | 15 тестов: parse_handoff_block, format_handoff_instructions, build_agent_prompt |
| `test_handoff_server.py` | **НЕ СУЩЕСТВУЕТ** | 0 тестов для generate_handoff_tools, handle_handoff_tool_call, max_cycles |
| `test_tasks.py` | Существует | 10 тестов: Task CRUD router endpoints |
| `test_task_service.py` | Существует | 6 тестов: status transitions, required fields validation |
| `test_workflow_service.py` | **НЕ ПРОВЕРЕНО** | Нужно проверить наличие тестов для workflow locking |
| `notificationEventHandler.test.ts` | Существует | Frontend notification handler тесты |
| `useWorkflowValidation.test.ts` | Существует | Canvas validation тесты |
| `useToast.test.tsx` | Существует | Toast hook тесты |

При изменении core-модулей (worker, event_bus, runtime, graph_service, handoff_server) автоматической защиты мало.
Worker и event_bus не имеют тестов — изменения требуют ручной проверки.

---

## Детали по каждому файлу

### 1. `api/app/worker.py` (~460 строк) — CRITICAL

**Что делает:** Task Worker — отдельный процесс, слушающий Redis commands, выполняющий LangGraph граф и публикующий события обратно в Redis. Единственный процесс, который исполняет бизнес-логику (orchestration). WS-прокси и API — только транспорт.

**Архитектура:**
```
Client ↔ WS (proxy) → Redis commands → Worker (LangGraph + SDK) → Redis events → WS → Client
                                                                 ↓
                                                          Redis buffer (replay)
```

**Ключевые классы/функции:**
- `EventPublisher` — имплементирует `send_json()`, заменяет WebSocket в graph nodes; публикует в Redis вместо WS напрямую
- `handle_session()` — entry point сессии: try/finally crash resilience, cleanup children + runtime + buffer
- `_run_session()` — core logic: загрузка agent/task/product, workdir resolution, runtime start, LangGraph streaming
- `_run_graph()` — `graph.astream()` wrapper, детекция interrupt через `"__interrupt__"`, error handling
- `_handle_graph_result()` — dispatch: interrupted → approval_required, completed → task done, errored → error event
- `_restore_interrupt_state()` — восстановление pending interrupts из LangGraph checkpoint при reconnect
- `run_worker()` — main loop: Redis subscribe `worker:sessions`, asyncio.create_task per session

**Связанные модули:**
- `event_bus.py` — publish_event, publish_notification, subscribe_commands, clear_buffer
- `redis_service.py` — init_redis, close_redis, get_redis
- `graph_service.py` — get_graph(), build_graph(), WorkflowState
- `runtime/` — start_session, stop_session, is_running, get_children
- `handoff_server.py` — generate_handoff_tools(), format_handoff_tools_prompt()
- `session_service.py` — get_session, add_message, stop_session
- `task_service.py` — update_task_status

**Риски:**
- **Single point of failure:** если worker.py падает, все активные сессии теряются
- **Crash cleanup:** try/finally в handle_session гарантирует cleanup, но если kill -9 Worker — orphaned sessions в Redis и runtime
- **Два checkpointer:** API (main.py lifespan) и Worker — оба инициализируют AsyncPostgresSaver. Если URL расходятся — данные теряются
- **Event buffer overflow:** 500 events cap в Redis list (LTRIM) — при длинных сессиях старые события теряются при reconnect
- **DB session lifetime:** одна async_session на весь lifetime handle_session — stale reads возможны

**Что проверить после изменения:**
- [ ] Worker стартует: `python -m app.worker` — подключается к Redis и PostgreSQL
- [ ] Chat flow: message → Worker выполняет → events в Redis → WS получает
- [ ] Handoff: approve/reject → Worker resume → events
- [ ] Stop: stop command → Worker cleanup → done event
- [ ] Crash resilience: kill Worker → restart → pending sessions recoverable через checkpoint
- [ ] WS disconnect: Worker продолжает работу, events буферизируются
- [ ] Reconnect: WS replay buffered events, Worker не перезапускается

**Какие тесты запустить:**
```bash
# test_worker.py НЕ СУЩЕСТВУЕТ — ручная проверка обязательна
cd api && pytest tests/test_ws.py -v  # proxy-сторона
cd api && pytest tests/test_runtime.py -v
```

---

### 1.5. `api/app/services/event_bus.py` + `redis_service.py` — CRITICAL

**Что делает:** Redis pub/sub абстракция (event_bus) + connection pool management (redis_service). Весь realtime transport между Worker, WS-прокси и notifications.

**event_bus.py — ключевые функции:**
- `publish_event(session_id, data)` — публикует в канал `session:{id}:events` + буферизирует в Redis list `session:{id}:buffer`
- `publish_command(session_id, data)` — публикует в канал `session:{id}:commands`
- `subscribe_commands(session_id)` — async generator: подписка на commands канал
- `subscribe_events(session_id)` — async generator: подписка на events канал
- `get_buffered_events(session_id)` — получает буфер из Redis list
- `clear_buffer(session_id)` — очищает буфер при завершении сессии
- `publish_notification(event_type, data)` — публикует в канал `notifications`
- `subscribe_notifications()` — async generator: подписка на notifications

**redis_service.py — ключевые функции:**
- `init_redis()` — создаёт connection pool (вызывается в main.py lifespan и worker.py)
- `close_redis()` — закрывает pool
- `get_redis()` — возвращает Redis client (raises если не инициализирован)

**Каналы Redis:**
- `session:{id}:events` — Worker → WS (streaming events)
- `session:{id}:commands` — WS → Worker (message/approve/reject/stop)
- `session:{id}:buffer` — Redis list, 500 events cap, 1h TTL (reconnect replay)
- `worker:sessions` — WS → Worker (start session notification)
- `notifications` — Worker → notifications WS (task_completed, task_error)

**Риски:**
- **Redis single point of failure:** если Redis упадёт — весь realtime ломается (chat, notifications)
- **Race condition в ws.py:** subscribe к events ДОЛЖЕН быть ДО чтения buffer, иначе пропуск событий (уже исправлено)
- **Buffer overflow:** LTRIM обрезает до 500 events — длинные сессии теряют старые события
- **No persistence:** Redis pub/sub fire-and-forget — если subscriber не слушает, event потерян
- **Connection pool exhaustion:** множество одновременных сессий × pubsub = много connections
- **TTL buffer:** 1h — если пользователь вернётся через 2h, buffer пуст

**Что проверить после изменения:**
- [ ] Worker получает commands от WS
- [ ] WS получает events от Worker в realtime
- [ ] Buffer replay при reconnect: все события доставлены
- [ ] Notifications: task_completed/task_error приходят в notifications WS
- [ ] Redis disconnect: graceful degradation (error events, не crash)
- [ ] clear_buffer: вызывается при завершении сессии

**Какие тесты запустить:**
```bash
# test_event_bus.py НЕ СУЩЕСТВУЕТ — ручная проверка обязательна
cd api && pytest tests/test_ws.py -v
cd api && pytest tests/test_notification_service.py -v
cd api && pytest tests/test_notifications_ws.py -v
```

---

### 2. `api/app/services/runtime/` (пакет, ~250 строк) — HIGH

**Что делает:** Управляет жизненным циклом Claude Agent SDK (ClaudeSDKClient), budget tracking, circuit breaker, telemetry (Langfuse).

**Структура пакета:**
```
runtime/
├── __init__.py          — re-export: AgentRuntime, runtime, AgentRuntimeError, TransientAgentError
└── agent_runner.py      — AgentRuntime + AgentSession + ClaudeSDKClient (~250 строк)
```
> **Удалены в миграции:** cli_builder.py, event_parser.py, process_manager.py (subprocess → SDK)

**Ключевые классы/функции:**
- `AgentRuntime` — singleton (`runtime = AgentRuntime()`)
- `AgentSession` — dataclass: session config (workdir, system_prompt, claude_session_id, allowed_tools)
- `ClaudeSDKClient` — typed Python API для Claude Agent SDK (заменяет subprocess)
- `start_session()` — регистрация сессии (конфиг, workdir)
- `send_message()` — SDK call, streaming событий, budget/circuit breaker
- `stop_session()` — остановка SDK client + cleanup children
- `get_children()` — дочерние сессии для cleanup

**Связанные модули:**
- `worker.py` — вызывает `runtime.start_session()`, `is_running()`, `stop_session()`, `get_children()`
- `graph_service.py` — вызывает `runtime.send_message()`, `start_session()`, `stop_session()`
- `sessions.py` (router) — импортирует `runtime` singleton напрямую
- `budget.py` — встроен через `self._budget` (BudgetTracker)
- `circuit_breaker.py` — встроен через `self._breaker` (CircuitBreaker)
- `auth_service.py` — lazy import, OAuth token для SDK
- `telemetry.py` — lazy import, Langfuse spans

**Что проверить после изменения:**
- [ ] Chat flow: message → SDK streaming → events → done
- [ ] Sub-agent handoff: approve → sub-agent стримит → handoff_done
- [ ] Budget tracking: предупреждения и лимиты срабатывают
- [ ] Circuit breaker: SDK errors → breaker opens → fail-fast
- [ ] Stop session: SDK client stops, children тоже
- [ ] OAuth: token передаётся в ClaudeAgentOptions через env dict

**Какие тесты запустить:**
```bash
cd api && pytest tests/test_runtime.py -v
cd api && pytest tests/test_ws.py -v
cd web && npm test -- --run useChat
```

---

### 2. `api/app/services/graph_service.py` (~501 строк) — HIGH

**Что делает:** LangGraph StateGraph с 6 nodes (run_agent, notify_handoff, gate, auto_handoff, complete, blocked), 2 routing functions, MCP handoff integration, checkpoint persistence. Управляет orchestration, HITL approve/reject, auto-transitions и notifications.

**Ключевые функции:**
- `run_agent_node()` — стримит SDK события через EventPublisher (→ Redis), сохраняет в DB, парсит handoff через `parse_handoff_from_text()` → `handle_handoff_tool_call()` → `HandoffResult`
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
- `worker.py` — вызывает `get_graph()`, передаёт EventPublisher/db/task_id через configurable
- `runtime/` — `send_message()`, `start_session()`, `stop_session()`
- `handoff_server.py` — `parse_handoff_from_text()`, `handle_handoff_tool_call()`, `generate_handoff_tools()` (ключевая зависимость)
- `notification_service.py` — `broadcast_notification()` (complete, blocked)
- `event_bus.py` — косвенно через EventPublisher в worker.py (graph nodes используют `ws.send_json()` → Redis)
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

### 3. `api/app/routers/ws.py` (~91 строк) — HIGH

**Что делает:** WebSocket thin proxy. Принимает WS-подключение, валидирует сессию, и работает как двунаправленный мост: Client ↔ Redis. Вся бизнес-логика — в worker.py.

**Ключевые функции:**
- `websocket_session()` — accept, validate session, notify worker (start), запуск двух concurrent tasks: event forwarder + command receiver
- `_forward_events()` — подписка на Redis events канал → forward в WebSocket
- `_receive_commands()` — приём WS messages → publish в Redis commands канал
- `_notify_worker_start()` — publish `{action: "start"}` в `worker:sessions` Redis channel

**Архитектурная роль:**
```
Client WS ←→ ws.py (proxy) ←→ Redis ←→ Worker (business logic)
```

**Связанные модули:**
- `event_bus.py` — subscribe_events, publish_command, get_buffered_events
- `redis_service.py` — get_redis (для worker:sessions publish)
- `session_service.py` — get_session (валидация при connect)
- `main.py` — router registration

**Риски:**
- **Subscribe-before-buffer:** подписка на events ДОЛЖНА быть ДО чтения buffer, иначе race condition — пропуск событий (исправлено)
- **WS disconnect ≠ session stop:** Worker продолжает работу после disconnect. Если Worker завершит и очистит buffer до reconnect — события потеряны
- **Тонкий прокси = мало защиты:** ws.py не валидирует содержимое commands, пробрасывает as-is в Redis

**Что проверить после изменения:**
- [ ] WS connect: подключение к существующей сессии
- [ ] WS connect: ошибка для несуществующей сессии (4004)
- [ ] Buffer replay: при reconnect — буферизированные events доставлены
- [ ] Live events: Redis events → WS в realtime
- [ ] Commands: WS messages → Redis commands
- [ ] Stop: stop command пробрасывается в Redis
- [ ] Invalid JSON: ошибка без crash
- [ ] Worker notification: start published при connect

**Какие тесты запустить:**
```bash
cd api && pytest tests/test_ws.py -v  # 7 тестов proxy-протокола
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
- Reconnect: exponential backoff (1s → 30s, 20 attempts), buffer replay восстанавливает missed events
- Worker не останавливается при WS disconnect — events буферизируются в Redis


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
- `WsIncoming` (frontend) должен точно соответствовать событиям из worker.py/graph_service.py (через Redis → ws.py proxy)
- `WsOutgoing` (frontend) должен соответствовать обработчикам в worker.py (через ws.py proxy)
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

**Что делает:** FastAPI app, lifespan (Redis init/close, PostgreSQL checkpointer init, graph compilation, seed_system_agent), CORS middleware, router registration (13 роутеров).

**Ключевые части:**
- `lifespan()` — `init_redis()` → `AsyncPostgresSaver.from_conn_string()` → `checkpointer.setup()` → `build_graph(checkpointer)` → `_compiled_graph` → `seed_system_agent()` → yield → `close_redis()`
- Router registration — 13 `app.include_router()` с prefix и tags
- CORS middleware — `settings.cors_origins`

**Связанные модули:**
- `graph_service.py` — `_compiled_graph`, `build_graph()`
- `redis_service.py` — `init_redis()`, `close_redis()` в lifespan
- `config.py` — `settings` (database_url, cors_origins)
- Все 13 роутеров: teams, agents, workflows, workflow_edges, agent_links, sessions, businesses, products, tasks, ws, notifications_ws, auth, memory, evaluations
- `system_agent_service.py` — `seed_system_agent()` в lifespan

**Известные проблемы:**
- Нет try/except/retry на `checkpointer.setup()` и `init_redis()` — если PostgreSQL или Redis недоступен при старте, приложение не стартует без retry
- Два процесса (API + Worker) инициализируют Redis и checkpointer независимо — если один из них не стартует, другой работает с неполной функциональностью


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
- `runtime/` — `settings.workspace_path`, budget/circuit breaker params
- `graph_service.py` — `settings.workspace_path`
- `main.py` — `settings.cors_origins`, `settings.database_url`
- `product_service.py` — `settings.workspace_path`, `settings.clone_timeout_seconds`
- `auth_service.py`, `memory_service.py`
- `mcp/tools/platform.py` — `settings.api_base_url` (MCP Server → API HTTP вызовы)


**Поля Settings (15 параметров, env-prefix `AC_`):**
`database_url`, `workspace_path`, `cors_origins`, `oauth_client_id`, `oauth_authorize_url`, `oauth_token_url`, `oauth_redirect_uri`, `oauth_scopes`, `voyage_api_key`, `cb_failure_threshold`, `cb_recovery_timeout`, `cb_failure_window`, `budget_session_limit_usd`, `clone_timeout_seconds`, `api_base_url`

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
- `worker.py` — вызывает `generate_handoff_tools()` и `format_handoff_tools_prompt()` при session start
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
- `worker.py` — вызывает `update_task_status()` через `_try_update_task_status()` (auto-update на interrupt/approve/error)
- `routers/tasks.py` — CRUD endpoints + PATCH /status
- `Dashboard.tsx` — Kanban drag & drop вызывает status transitions
- `TaskCard.tsx` — кнопка "Start" → backlog→in_progress

**Риски:**
- **Изменение VALID_TRANSITIONS** ломает worker.py auto-update (HTTPException при invalid transition → error log)
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

