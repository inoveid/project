# DANGER_ZONES.md

Файлы с высоким blast radius. Изменение любого из них может сломать ключевые функции приложения.
Источник истины — текущий код. Конвенции и структура — см. [CLAUDE.md](CLAUDE.md).

---

## Сводная таблица

| Файл | Blast Radius | Что может сломаться |
|------|-------------|-------------------|
| `api/app/services/runtime/` (пакет) | **HIGH** | Весь chat flow, budget tracking, circuit breaker, telemetry |
| `api/app/services/graph_service.py` | **HIGH** | Orchestration, handoff, HITL gate, sub-agent lifecycle |
| `api/app/routers/ws.py` | **HIGH** | Все WebSocket клиенты, reconnect, approve/reject flow |
| `web/src/hooks/chat/` (пакет) | **HIGH** | Весь chat UI, streaming, handoff визуализация |
| `web/src/types/index.ts` | **MEDIUM** | Frontend type contracts (29 type declarations (25 interfaces + 4 type aliases), WsIncoming/WsOutgoing) |
| `api/app/main.py` (lifespan) | **MEDIUM** | Startup, graph init, seed_system_agent, router registration |
| `api/app/database.py` | **MEDIUM** | Все DB-зависимые модули (9+ импортеров: все routers, auth_service, eval_service) |
| `api/app/config.py` | **MEDIUM** | Все модули через `settings` singleton (11+ импортеров) |
| `api/app/services/product_service.py` (`_do_clone`) | **MEDIUM** | Фоновые clone-задачи: утечки задач, зависшие статусы, stale DB sessions |

### Состояние тестов для danger zones

| Тест-файл | Статус | Проблема |
|-----------|--------|----------|
| `test_ws.py` | Частично | 6 тестов WS-протокола работают. Удалён `test_ws_message_streams_response` (патчил P3-функцию `_stream_response`) |
| `test_runtime.py` | Существует | — |
| `test_graph_service.py` | **НЕ СУЩЕСТВУЕТ** | 0 тестов для nodes, routing, interrupt |
| `test_handoff.py` | Существует | 15 тестов: parse_handoff_block, format_handoff_instructions, build_agent_prompt |

При изменении core-модулей (runtime, graph_service, ws) автоматической защиты практически нет.

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

### 2. `api/app/services/graph_service.py` (~307 строк) — HIGH

**Что делает:** LangGraph StateGraph с 3 nodes (run_agent, notify_handoff, gate), 2 routing functions, checkpoint persistence. Управляет orchestration и HITL approve/reject.

**Ключевые функции:**
- `run_agent_node()` — стримит CLI события в WebSocket, сохраняет в DB, парсит handoff
- `notify_handoff_node()` — отправляет `approval_required` в WebSocket
- `gate_node()` — `interrupt()` для HITL, создание sub-session, запуск sub-agent runtime
- `route_after_agent()` / `route_after_gate()` — conditional edges
- `build_graph()` — компиляция графа с checkpointer
- `WorkflowState` — TypedDict, персистируется в PostgreSQL

**Связанные модули:**
- `ws.py` — вызывает `get_graph()`, передаёт websocket/db через configurable
- `runtime/` — `send_message()`, `start_session()`, `stop_session()`
- `utils/handoff.py` — `parse_handoff_block()`, `build_agent_prompt()` (критичные утилиты для handoff)
- `session_service.py` — `create_session()`, `add_message()`, `get_session()`, `stop_session()`
- `agent_link_service.py` — `get_agent_handoff_targets()`
- `main.py` — lifespan инициализирует `_compiled_graph`


**Что проверить после изменения:**
- [ ] Простой chat (без handoff): message → streaming → done
- [ ] Handoff flow: agent предлагает handoff → approval_required → approve → sub-agent → handoff_done → done
- [ ] Reject flow: approval_required → reject → done
- [ ] Cycle detection: A→B→A — handoff_cycle_detected
- [ ] Depth limit: depth >= MAX_DEPTH(5) → END без handoff
- [ ] Sub-agent DB cleanup: sub-session закрывается в DB (status=stopped)
- [ ] Checkpoint persistence: interrupt → restart server → state сохранён

**Какие тесты запустить:**
```bash
# test_graph_service.py НЕ СУЩЕСТВУЕТ — ручная проверка обязательна
cd api && pytest tests/test_handoff.py -v
cd api && pytest tests/test_ws.py -v
```

---

### 3. `api/app/routers/ws.py` (~200 строк) — HIGH

**Что делает:** WebSocket endpoint `/api/ws/sessions/{session_id}`. Управляет подключением, state machine (interrupted flag), маршрутизацией WS-сообщений, LangGraph streaming.

**Ключевые функции:**
- `websocket_session()` — accept, load session/agent, start runtime, handle disconnect cleanup
- `_handle_messages()` — основной цикл: message/approve/reject/stop dispatch
- `_run_graph()` — `graph.astream()` wrapper, детекция interrupt через `"__interrupt__" in chunk`

**Связанные модули:**
- `graph_service.py` — `get_graph()`, `WorkflowState`
- `runtime/` — `start_session()`, `is_running()`, `stop_session()`, `get_children()`
- `session_service.py` — `get_session()`, `add_message()`, `stop_session()`
- `agent_link_service.py` — `get_agent_handoff_targets()`
- `utils/handoff.py` — `format_handoff_instructions()`
- `main.py` — router registration (`app.include_router`)

**Особенности:**
- `interrupted` — boolean in-memory flag. При WS disconnect и reconnect сбрасывается в `False`. Если граф был в interrupt (ждал approve/reject), это состояние **теряется** — пользователь не узнает, что граф паузирован
- `db: AsyncSession` — одна на весь WS lifecycle (может быть часы). Stale reads возможны после interrupt/resume


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
├── chatEventHandler.ts (~222) — handleEvent switch (13 cases), pure function (без React hooks)
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

### 5. `web/src/types/index.ts` (~250 строк) — MEDIUM

**Что делает:** Все TypeScript интерфейсы и type unions. 29 type declarations (25 interfaces + 4 type aliases), включая `WsIncoming` (13 event types), `WsOutgoing` (4 message types), `ChatItem`, `HandoffItem`.

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

### 6. `api/app/main.py` (~45 строк) — MEDIUM

**Что делает:** FastAPI app, lifespan (PostgreSQL checkpointer init, graph compilation, seed_system_agent), CORS middleware, router registration (10 роутеров).

**Ключевые части:**
- `lifespan()` — `AsyncPostgresSaver.from_conn_string()` → `checkpointer.setup()` → `build_graph(checkpointer)` → `_compiled_graph` → `seed_system_agent()` (создаёт System Agent если нет)
- Router registration — 10 `app.include_router()` с prefix и tags
- CORS middleware — `settings.cors_origins`

**Связанные модули:**
- `graph_service.py` — `_compiled_graph`, `build_graph()`
- `config.py` — `settings` (database_url, cors_origins)
- Все 10 роутеров: teams, agents, agent_links, sessions, businesses, products, ws, auth, memory, evaluations
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
- Все 9 REST роутеров + ws.py (через `Depends(get_db)`)
- `auth_service.py`, `eval_service.py`, `import_cmd.py`, `product_service._do_clone()` (через `async_session` напрямую)


**Что проверить после изменения:**
- [ ] Все API endpoints отвечают (любое изменение engine/session ломает всё)
- [ ] WebSocket handler получает рабочую db session
- [ ] Background tasks (evaluations) получают рабочую session

**Какие тесты запустить:**
```bash
cd api && pytest -v  # все тесты зависят от database setup
```

---

### 8. `api/app/config.py` (30 строк) — MEDIUM

**Что делает:** Pydantic Settings с env-prefix `AC_`. Единственный `settings` singleton, импортируемый 11+ модулями.

**Связанные модули:**
- `database.py` — `settings.database_url`
- `runtime/` — `settings.workspace_path`, `settings.claude_cli_path`, budget/circuit breaker params
- `graph_service.py` — `settings.workspace_path`
- `main.py` — `settings.cors_origins`, `settings.database_url`
- `product_service.py` — `settings.workspace_path`, `settings.clone_timeout_seconds`
- `auth_service.py`, `memory_service.py`


**Поля Settings (15 параметров, env-prefix `AC_`):**
`database_url`, `claude_cli_path`, `workspace_path`, `cors_origins`, `oauth_client_id`, `oauth_authorize_url`, `oauth_token_url`, `oauth_redirect_uri`, `oauth_scopes`, `voyage_api_key`, `cb_failure_threshold`, `cb_recovery_timeout`, `cb_failure_window`, `budget_session_limit_usd`, `clone_timeout_seconds`

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

