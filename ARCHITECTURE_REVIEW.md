# Архитектурный анализ Agent Console: AI-first разработка

**Дата:** 2026-03-08
**Версия:** 10.0
**Метод:** Десятипроходный анализ (архитектура, оркестрация, data layer, Chat/WebSocket, Memory/Eval/MCP, тесты/инфраструктура, безопасность, Frontend CRUD)

---

## Содержание

1. [Краткая оценка](#1-краткая-оценка)
2. [Карта архитектуры](#2-карта-архитектуры)
3. [Основные модули и их размеры](#3-основные-модули-и-их-размеры)
4. [Потоки данных](#4-потоки-данных)
5. [Контекст: реализация P1-P8](#5-контекст-реализация-p1-p8)
6. [Архитектурные проблемы](#6-архитектурные-проблемы)
7. [AI-first критерии](#7-ai-first-критерии)
8. [AI-agent паттерны](#8-ai-agent-паттерны)
9. [Рекомендации](#9-рекомендации)
10. [Приоритетный список улучшений](#10-приоритетный-список-улучшений)
11. [Требует дополнительного изучения](#11-требует-дополнительного-изучения)

---

## 1. Краткая оценка

**Проект:** Agent Console — web-приложение для управления AI-агентами.
**Стек:** Python FastAPI (backend) + React TypeScript (frontend) + PostgreSQL + pgvector.
**Размер:** ~13,000 строк кода (7,330 Python + 5,727 TypeScript), 120+ файлов.
**Зрелость:** Прошёл все 8 этапов роадмапа (P1-P8), включая LangGraph оркестрацию, vector memory, evaluation framework, circuit breaker, budget control.

| Критерий | Оценка | Комментарий |
|----------|--------|-------------|
| Структура директорий | 8/10 | Чёткое разделение api/web, слоёная архитектура |
| Модульность | 5/10 | CRUD-модули хороши; runtime (365, 4 класса), graph_service (303) — монолиты; @retry мёртвая логика |
| Типизация | 8/10 | TypeScript strict + noUncheckedIndexedAccess, Pydantic v2, SQLAlchemy Mapped. ⚠ `as WsIncoming` без runtime validation (useChat.ts:251), `undefined as T` (client.ts:21) |
| Тестовое покрытие | 4/10 | 182 backend-теста (13 файлов), test_ws.py полностью нерабочий (ImportError), 0 тестов graph_service/orchestrator/memory, budget+circuit_breaker — качественные pure unit |
| Документация | 6/10 | Хороший CLAUDE.md, но нет ARCHITECTURE.md, WS protocol, state contracts |
| AI-agent readiness | 5/10 | Конвенции описаны, нет explicit contracts, inconsistent return types в сервисах |
| Observability | 4/10 | Langfuse — минимальная интеграция (25 строк init, trace+generation в runtime), нет structured logging |
| Change isolation | 5/10 | CRUD изолированы; core services сильно связаны, kill-all ломает параллельные сессии |
| Security posture | 3/10 | Нет authN на API/WebSocket, single-user design, токены plain text в БД, нет rate limiting, нет CSP. PKCE flow корректен, CORS ограничен, path traversal защищён |
| **Общая оценка** | **5/10** | Хорошая база для CRUD; core chat flow без тестов, архитектурные проблемы в оркестрации |

---

## 2. Карта архитектуры

```
┌──────────────────────────────────────────────────────────────────┐
│                     Frontend (React + Vite)                       │
│                                                                   │
│  Pages (4)         Hooks (8+useChat)    API Layer (7)            │
│  ┌──────────┐     ┌──────────────┐     ┌──────────┐             │
│  │Dashboard │────→│useTeams      │────→│teams.ts  │──┐          │
│  │TeamPage  │     │useAgents     │     │agents.ts │  │          │
│  │ChatPage  │     │useSessions   │     │sessions  │  │ HTTP     │
│  │EvalDash  │     │useAuth       │     │auth.ts   │  │ REST     │
│  └──────────┘     │useAgentLinks │     │eval.ts   │  │          │
│       │           │useWorkspaces │     │links.ts  │  │          │
│       ▼           │useEvaluations│     │workspaces│  │          │
│  Components(30+)  └──────────────┘     └──────────┘  │          │
│  ┌──────────┐     ┌──────────────┐                    │          │
│  │ChatPanel │────→│useChat (339) │──── WebSocket ─────┼──┐      │
│  │ChatWindow│     │  9 refs      │                    │  │      │
│  │HandoffBlk│     │  4 useState  │                    │  │      │
│  │SessionLst│     │  13 events   │                    │  │      │
│  └──────────┘     └──────────────┘                    │  │      │
└───────────────────────────────────────────────────────┼──┼──────┘
                                                        │  │
                              HTTP REST ────────────────┘  │ WS
                              WebSocket ───────────────────┘
                                                        │  │
┌───────────────────────────────────────────────────────┼──┼──────┐
│                     Backend (FastAPI)                  │  │      │
│                                                       ▼  ▼      │
│  Routers (9)              Services (14)                         │
│  ┌─────────────┐         ┌──────────────────────────────┐      │
│  │teams.py     │────────→│team_service (107)             │      │
│  │agents.py    │────────→│agent_service (104)            │      │
│  │sessions.py  │────────→│session_service (95)           │      │
│  │agent_links  │────────→│agent_link_service (104)       │      │
│  │auth.py      │────────→│auth_service (209) ⚠ GLOBAL   │      │
│  │memory.py    │────────→│memory_service (199)           │      │
│  │evaluations  │────────→│eval_service (311)→judge(198)  │      │
│  │workspaces   │         │                               │      │
│  └─────────────┘         └──────────────────────────────┘      │
│                                                                  │
│  ┌─────────────┐         ┌──────────────────────────────┐      │
│  │ws.py (195)  │────────→│graph_service (303, 7 funcs)   │      │
│  │  WS handler │         │  Nodes (3):                   │      │
│  │  interrupted│         │  ├─ run_agent_node            │      │
│  │  state flag │         │  ├─ notify_handoff_node       │      │
│  └─────────────┘         │  ├─ gate_node (HITL)          │      │
│                          │  Routing (2):                  │      │
│                          │  ├─ route_after_agent          │      │
│                          │  └─ route_after_gate           │      │
│                          │         │                     │      │
│                          │         ▼                     │      │
│                          │  runtime (366) ⚠ KILLS ALL   │      │
│                          │  ├─ budget (208)              │      │
│                          │  ├─ circuit_breaker (151)     │      │
│                          │  ├─ telemetry (25)            │      │
│                          │  └─ auth_service (lazy)       │      │
│                          │                               │      │
│                          │  orchestrator (203)           │      │
│                          │  ├─ format_handoff_inst ✓USED │      │
│                          │  ├─ parse_handoff_block ✓USED │      │
│                          │  ├─ _build_agent_prompt ✓USED │      │
│                          │  └─ handle_handoff ✗DEAD CODE │      │
│                          └──────────────────────────────┘      │
│                                        │                        │
│  ┌──────────────────┐                  │                        │
│  │Models (11 ORM)   │←─── SQLAlchemy ──┘                        │
│  │Schemas (Pydantic)│                                           │
│  └────────┬─────────┘                                           │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐  ┌────────────────┐                      │
│  │PostgreSQL+pgvector│  │LangGraph       │                      │
│  │ 11 таблиц + LG   │  │Checkpoints (PG)│                      │
│  │ ✓ FK индексы (мигр)│ └────────────────┘                      │
│  │ ✓ HNSW (мигр 003) │                                          │
│  └──────────────────┘                                           │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────┐    ┌─────────────────────┐
│  MCP Server (автономный) │    │  External APIs      │
│  server.py (63)          │    │  ├─ Claude CLI       │
│  tools/tasks.py (149)    │    │  ├─ Claude API       │
│  tools/specs.py (85)     │    │  │   (judge_service) │
│  ─── stdio ──→ Claude    │    │  ├─ Voyage AI        │
│                Code      │    │  │   (memory_service) │
└──────────────────────────┘    │  └─ Langfuse (opt)   │
                                └─────────────────────┘
```

---

## 3. Основные модули и их размеры

### Backend (Python) — 7,330 строк

#### Core Infrastructure

| Файл | Строк | Ответственность |
|------|-------|----------------|
| main.py | 45 | FastAPI app, lifespan, router mounting |
| config.py | 30 | Pydantic Settings (prefix AC_) |
| database.py | 12 | AsyncEngine + session factory |

#### Services (14 модулей, ~2,600 строк)

| Файл | Строк | Классы | Функции | Ответственность |
|------|-------|--------|---------|----------------|
| runtime.py | 365 | 4 | 12 | CLI subprocess lifecycle, budget, circuit breaker. ⚠ @retry на _launch_process — мёртвая логика (retry_if TransientAgentError, но _launch_process не бросает его) |
| eval_service.py | 312 | 0 | 11 | EvalCase/EvalRun CRUD, batch execution, comparison |
| graph_service.py | 303 | 0 | 7 | LangGraph StateGraph, 3 nodes + 2 routing + build + get_graph, checkpoint, HITL |
| auth_service.py | 209 | 2 exc | 7 | OAuth2 PKCE, token refresh, ⚠ global state |
| budget.py | 208 | 4 | 5 | BudgetTracker, cost computation, warning/critical events |
| orchestrator_service.py | 203 | 0 | 4 | ⚠ 129 строк мёртвого кода + 3 утилиты (format_handoff_instructions, parse_handoff_block, _build_agent_prompt) |
| memory_service.py | 199 | 1 dc | 6 | pgvector RAG, Voyage AI embeddings |
| judge_service.py | 198 | 0 | 3 | LLM-as-Judge via Anthropic SDK |
| circuit_breaker.py | 151 | 2 | 8 | CLOSED/OPEN/HALF_OPEN state machine |
| team_service.py | 107 | 2 exc | 6 | Team CRUD |
| agent_link_service.py | 104 | 3 exc | 7 | AgentLink CRUD + routing |
| agent_service.py | 104 | 3 exc | 7 | Agent CRUD |
| session_service.py | 95 | 2 exc | 6 | Session + Message CRUD |
| telemetry.py | 25 | 0 | 1 | Langfuse init wrapper (минимальная интеграция: trace+generation в runtime.send_message) |

#### Routers (9 модулей, ~850 строк)

| Файл | Строк | Endpoints | Особенности |
|------|-------|-----------|-------------|
| ws.py | 195 | 1 WS | LangGraph streaming, interrupted state machine |
| evaluations.py | 115 | 8 REST | Background task execution |
| memory.py | 106 | 3 REST | Inline Pydantic schemas |
| agents.py | 86 | 6 REST | Two scopes: /agents + /teams/{id}/agents |
| workspaces.py | 78 | 2 REST | Git clone/init |
| teams.py | 66 | 5 REST | Standard CRUD |
| agent_links.py | 57 | 3 REST | Team-scoped |
| sessions.py | 55 | 4 REST | Status lifecycle |
| auth.py | 51 | 4 REST | OAuth PKCE flow |

#### Models (11 ORM классов, 11 таблиц + LangGraph checkpoint таблицы, ~370 строк) & Schemas (Pydantic, ~300 строк)

11 ORM-моделей: Team, Agent, AgentLink, Session, Message, OAuthToken, EpisodicMemory, SemanticMemory, EvalCase, EvalRun, EvalResult.

Standard Create/Update/Read pattern, Pydantic v2, from_attributes=True.

⚠ **Inconsistent return types в сервисах:** team_service возвращает dict (через _team_to_dict()), agent_service — ORM objects, session_service — mixed (create→Session, get_sessions→list[dict]).

#### Tests (13 файлов, 182 тестовых функции)

Преимущественно mock-based. 0 тестов с реальной БД. Исключения: test_budget.py (19), test_circuit_breaker.py (14) — pure unit без моков; test_agent_link_service.py (12), test_auth_service.py (15) — service-level тесты с мокнутой DB session.

| Файл | Тестов | Подход |
|------|--------|--------|
| test_runtime.py | 20 | Unit, тестирует AgentRuntime (start/stop/parse/build_command/run_task) |
| test_budget.py | 19 | Pure unit, без моков: BudgetTracker, compute_cost, edge cases |
| test_evaluations.py | 19 | Router-level mock + schema validation + judge response parsing |
| test_import_cmd.py | 17 | Mixed: pure unit (parse/discover) + service с мокнутой DB |
| test_auth_service.py | 15 | Service-level: мокнутый httpx + DB session, тестирует OAuth PKCE |
| test_agents.py | 14 | Router-level mock |
| test_circuit_breaker.py | 14 | Pure unit, без моков: state machine CLOSED/OPEN/HALF_OPEN |
| test_agent_links.py | 12 | Router-level mock + schema validation |
| test_agent_link_service.py | 12 | Service-level: мокнутая DB session |
| test_ws.py | 12 | ⚠ **ВСЕ 12 нерабочие** — ImportError при загрузке модуля (6.11) |
| test_teams.py | 11 | Router-level mock + schema validation |
| test_auth.py | 9 | Router-level mock |
| test_sessions.py | 8 | Router-level mock |

⚠ **test_ws.py полностью нерабочий:** `from app.routers.ws import _parse_handoff_block` (строка 9) вызывает ImportError — функция перенесена в orchestrator_service.py. Все 12 тестов не выполняются. См. секцию 6.11.

⚠ **0 тестов** для: graph_service, orchestrator_service, memory_service, MCP server.

### Frontend (TypeScript) — 5,727 строк

| Категория | Файлов | Строк | Ключевые файлы |
|-----------|--------|-------|----------------|
| Pages | 4 | 487 | Dashboard(141), TeamPage(172), ChatPage(66), EvalDashboard(108) |
| Hooks | 9 | 734 | useChat(339), useEvaluations(88), useAgents(61) |
| Components | 30+ | 1,900+ | ChatPanel(202), AgentForm(191), EvalRunDetail(156) |
| API Layer | 7 | 221 | client.ts(25) + resource modules |
| Types | 1 | 249 | 28 interfaces/types, 13 WS event types |
| Tests | 19 | ~1,000 | useChat.test(349), ChatPage.test(177) |

### MCP Server (автономный) — 297 строк

| Файл | Строк | Ответственность |
|------|-------|----------------|
| server.py | 63 | FastMCP registration, resources |
| tools/tasks.py | 149 | list_tasks, get_task, update_task_status |
| tools/specs.py | 85 | list_specs, get_spec (path traversal protection) |

---

## 4. Потоки данных

### 4.1 CRUD поток (Teams, Agents, Sessions, Links)

```
Client HTTP → Router → Service → SQLAlchemy → PostgreSQL → Response
```

Context locality: 5 файлов (model, schema, service, router, main.py).
Change isolation: высокая.

### 4.2 Chat поток (основной)

```
Client WS connect
  → ws.py: accept, load session, start runtime
  → Client sends "message"
  → ws.py: save to DB, build WorkflowState, call _run_graph()
  → graph.astream() → run_agent_node:
    → runtime.send_message():
      → kill ALL processes (⚠)
      → get OAuth token (auth_service)
      → check budget + circuit breaker
      → launch Claude CLI subprocess
      → stream JSON events from stdout
      → yield events
    → send events to WebSocket
    → save response to DB
    → parse handoff block
  → route_after_agent: handoff? → notify_handoff → gate_node
  → gate_node: interrupt() → checkpoint state to PostgreSQL
  → Client sends "approve"/"reject"
  → ws.py: Command(resume=True/False)
  → gate_node resumes: create sub-agent session, start runtime
  → run_agent_node (sub-agent, depth+1)
  → route_after_agent: END
  → Client receives "done"
```

Context locality: 8+ файлов (ws.py, graph_service, runtime, orchestrator utils, auth_service, budget, circuit_breaker, session_service).
Change isolation: низкая.

### 4.3 Memory поток

```
Agent tool call → memory router → memory_service
  → _embed(query) → asyncio.to_thread(voyageai.Client.embed)
  → _search_episodic() + _search_semantic() → pgvector cosine distance
  → merge + sort by similarity → response
```

Context locality: 3 файла (router, service, models).
Change isolation: высокая.

### 4.4 Evaluation поток

```
POST /eval/runs → evaluations router → eval_service.execute_eval_run()
  → load EvalCases from DB
  → for each case:
    → get agent output (provider or mock)
    → judge_service.judge_agent_output() → Anthropic API (Claude Sonnet)
    → parse rubric scores, compute weighted average
    → save EvalResult to DB
  → update EvalRun stats → response
```

Context locality: 4 файла (router, eval_service, judge_service, schemas).
Change isolation: средняя.

### 4.5 WebSocket Protocol (13 событий)

**Исходящие от клиента (WsOutgoing):**

| Тип | Когда | Payload |
|-----|-------|---------|
| message | Пользователь отправляет текст | { type, content } |
| stop | Пользователь останавливает агента | { type } |
| approve | HITL: одобрить handoff | { type } |
| reject | HITL: отклонить handoff | { type } |

**Входящие от сервера (WsIncoming):**

| Тип | Когда | Payload |
|-----|-------|---------|
| assistant_text | Streaming текст от агента | { type, content } |
| tool_use | Агент вызвал инструмент | { type, tool_name, tool_input } |
| tool_result | Результат инструмента | { type, content } |
| done | Агент завершил ответ | { type } |
| error | Ошибка | { type, error } |
| approval_required | HITL gate: нужно одобрение | { type, from_agent, to_agent, task } |
| handoff_start | Начало handoff к sub-agent | { type, from_agent, to_agent, task } |
| sub_agent_assistant_text | Streaming от sub-agent | { type, content, agent_name } |
| sub_agent_tool_use | Sub-agent вызвал инструмент | { type, tool_name, tool_input, agent_name } |
| sub_agent_tool_result | Результат инструмента sub-agent | { type, content, agent_name } |
| sub_agent_error | Ошибка sub-agent | { type, error, agent_name } |
| handoff_done | Handoff завершён | { type, agent_name } |
| handoff_cycle_detected | Обнаружен цикл handoff | { type, message } |

**Недокументированные события:**

Backend также отправляет события, не определённые в `WsIncoming`:

| Тип | Источник | Payload | Frontend |
|-----|----------|---------|----------|
| budget_warning | budget.py:197-203 → runtime.py:148 → graph_service.py:102 | { type, level, spent_usd, limit_usd, usage_percent } | ⚠ Молча игнорируется |
| budget_exceeded | budget.py:180-186 → runtime.py:148 → graph_service.py:102 | { type, level, spent_usd, limit_usd, call_count } | ⚠ Молча игнорируется |
| sub_agent_budget_warning | То же, с prefix sub_agent_ для depth > 0 | То же + agent_name | ⚠ Молча игнорируется |
| sub_agent_budget_exceeded | То же, с prefix sub_agent_ для depth > 0 | То же + agent_name | ⚠ Молча игнорируется |

Путь: `budget.record_usage()` → yield в `runtime.send_message()` → пересылка в `run_agent_node` → `ws.send_json()` → frontend. Frontend `handleEvent` switch не имеет case для этих типов → silent drop.

**State machine в ws.py:**

```
interrupted = False
  │
  ├─ "message" → save to DB → _run_graph(initial_state) → interrupted = result
  ├─ "stop" → kill process → send "done" → break
  │
  └─ interrupted = True:
      ├─ "approve" → _run_graph(Command(resume=True)) → interrupted = result
      ├─ "reject" → _run_graph(Command(resume=False)) → interrupted = result
      └─ "message" → send error "waiting for approval"
```

---

## 5. Контекст: реализация P1-P8

Проект развивался по роадмапу из `learning_roadmap.md`. Каждое архитектурное решение привязано к конкретному этапу:

| Этап | Цель | Реализация | Статус | Что не реализовано |
|------|------|-----------|--------|-------------------|
| P1 | AgentRuntime refactor | runtime.py: tenacity retry, exponential backoff, TransientAgentError | Partial | Backpressure для pipes не реализован. ⚠ @retry на _launch_process — мёртвая логика: метод бросает OSError, но retry ловит только TransientAgentError |
| P2 | Observability | telemetry.py + budget.py: Langfuse trace+generation в send_message, token pricing | Partial | gen_ai semantic conventions неполные, structured logging отсутствует, budget.record_usage не получает model name (cost opus занижена 5x) |
| P3 | Automatic Orchestrator | orchestrator_service.py: parse_handoff_block, auto-routing | Replaced | Заменён P4 (LangGraph). handle_handoff() = мёртвый код |
| P4 | LangGraph Redesign | graph_service.py: StateGraph, PostgreSQL checkpointing, interrupt() | Done | Time-travel debugging UI не реализован |
| P5 | Vector Memory | memory_service.py: pgvector, Voyage AI, episodic + semantic | Done | Hybrid search (BM25 + dense) — нет, только dense. ✓ HNSW index настроен (миграция 003, m=16, ef_construction=64). ⚠ `input_type="document"` для query embeddings (6.40). ⚠ 0 тестов |
| P6 | Evaluation Framework | eval_service.py + judge_service.py + golden dataset | Done | Trajectory evaluation не реализована (только outcome). ⚠ judge return type annotation ложная (6.41). ⚠ Background task без error handling (6.43) |
| P7 | MCP Server | mcp-workspace/: tasks, specs tools | Done | Полнофункционален. ⚠ 0 тестов |
| P8 | Production Hardening | circuit_breaker.py + budget.py | Partial | Stateless Redis — нет. Semantic caching — нет |

---

## 6. Архитектурные проблемы

### 6.1 runtime.send_message() убивает ВСЕ процессы (BUG)

**Файл:** `api/app/services/runtime.py:84-86`
```python
# Kill ALL stale CLI processes (any session may lock the workdir)
for r in self._processes.values():
    await self._kill_process(r)
```

Каждый вызов `send_message()` убивает процессы **всех** зарегистрированных сессий. Если пользователь использует side-by-side chat (ChatPage поддерживает 2 панели), отправка сообщения в одну панель убивает CLI-процесс другой.

**Уточнение:** `_kill_process()` (runtime.py:175-186) проверяет `proc.returncode is not None` и пропускает уже завершённые процессы. В handoff-потоке главный агент завершается естественно перед запуском sub-агента, поэтому kill-all в этом сценарии безвреден. Баг проявляется только при **параллельных WebSocket-сессиях**, когда два процесса действительно работают одновременно.

**Severity:** BUG (только при параллельных сессиях)
**Fix:** Убивать только процесс текущей сессии.

### 6.2 useChat tool_result не вызывает re-render (BUG)

**Файл:** `web/src/hooks/useChat.ts:82-87`
```tsx
case "tool_result": {
  const lastTool = pendingToolsRef.current[pendingToolsRef.current.length - 1];
  if (lastTool) {
    lastTool.result = event.content;
  }
  break;
}
```

Мутация ref без вызова `setItems()`. Результат tool_result не отображается в UI до следующего re-render. Для главного агента tool_result рендерится при получении `done` (useChat.ts:90-116 копирует tools из ref), поэтому severity ниже — delayed rendering, не потеря данных. Для sub-agent tool_result (useChat.ts:189-195) та же проблема — мутация ref без setItems, рендер только при `handoff_done`.

**Severity:** UX ISSUE (delayed rendering, не потеря данных)
**Fix:** Добавить `setItems()` после мутации ref в обоих случаях (tool_result и sub_agent_tool_result) для real-time rendering.

**Связанная проблема (v6):** 6.39 — `tool_use` и `sub_agent_tool_use` (строки 74-80, 179-186) аналогично мутируют refs без `setItems()`. Вся группа pending-ref мутаций (tool_use, tool_result, sub_agent_tool_use, sub_agent_tool_result) не вызывает re-render.

### 6.3 auth_service — глобальное состояние (RISK)

**Файл:** `api/app/services/auth_service.py:21-22`
```python
_code_verifier: Optional[str] = None
_oauth_state: Optional[str] = None
```

Module-level переменные. Два одновременных вызова `start_oauth_login()` перезапишут друг друга. Нет `asyncio.Lock` или atomic operations. Также `get_current_access_token()` вызывается из runtime.py при каждом send_message — при параллельных сессиях возможен race condition на token refresh.

**Уточнение:** Система single-user by design — в БД хранится максимум один OAuthToken (`delete(OAuthToken)` без WHERE, строки 113/167/208). OAuth flow запускается пользователем вручную через UI (AuthLoginModal). Вероятность двух одновременных OAuth flows крайне мала. Race condition на token refresh при side-by-side маловероятен — kill-all (runtime.py:84-86) сериализует выполнение send_message. Реальная severity ниже заявленной.

**Severity:** RISK (LOW для single-user, проявляется при multi-user)

### 6.4 orchestrator handle_handoff() — мёртвый код (DEBT)

**Файл:** `api/app/services/orchestrator_service.py:57-185`

129 строк рекурсивной оркестрации (строки 57-185), 0 внешних вызовов в текущем коде (единственный вызов — рекурсивный самовызов на строке 176). Заменён LangGraph (P4). Используются 3 утилитные функции: `format_handoff_instructions()` (ws.py:52), `parse_handoff_block()` (graph_service.py:141), `_build_agent_prompt()` (graph_service.py:220). Также `run_task()` в runtime.py:200-229 (30 строк) — мёртвый код P3, не используется после перехода на LangGraph.

**Severity:** TECH DEBT
**Fix:** Вынести 3 утилиты в `utils/handoff.py`, удалить handle_handoff() и runtime.run_task().

### 6.5 AgentLink.from/to_agent_id — нет индексов (PERFORMANCE)

Все FK-колонки имеют индексы в миграциях (001, 003, 004), **кроме** `AgentLink.from_agent_id` и `AgentLink.to_agent_id`. JOIN по from/to_agent_id в graph_service (поиск handoff targets) будет sequential scan.

**Severity:** PERFORMANCE
**Fix:** `op.create_index("idx_agent_links_from_agent_id", "agent_links", ["from_agent_id"])` + аналогично для `to_agent_id`.

### 6.6 database.py — нет pool_pre_ping (RELIABILITY)

**Файл:** `api/app/database.py`
```python
engine = create_async_engine(settings.database_url, echo=False)
```

Нет `pool_pre_ping=True` — stale connections не обнаруживаются. Pool size = 5 (SQLAlchemy default), max_overflow = 10. Нет pool_recycle.

**Severity:** RELIABILITY (stale connections после restart PostgreSQL)

### 6.7 Lifespan без error handling (RELIABILITY)

**Файл:** `api/app/main.py`
```python
async with AsyncPostgresSaver.from_conn_string(postgres_url) as checkpointer:
    await checkpointer.setup()  # нет try/except, нет retry
```

Если PostgreSQL недоступен при старте — приложение не стартует без retry.

**Severity:** RELIABILITY

### 6.8 Zero React Error Boundaries (STABILITY)

Ноль Error Boundary компонентов во всём фронтенде. Ошибка рендера в ChatMessage (markdown parsing), HandoffBlock, или ToolUseBlock крашит **всё приложение** без fallback UI.

**Severity:** STABILITY

### 6.9 memory_service создаёт Voyage client на каждый вызов (PERFORMANCE)

**Файл:** `api/app/services/memory_service.py`
```python
async def _embed(text_input: str) -> list[float]:
    client = voyageai.Client(api_key=settings.voyage_api_key)
    result = await asyncio.to_thread(client.embed, ...)
```

Новый HTTP client на каждый embedding запрос — нет connection reuse.

**Severity:** PERFORMANCE

### 6.10 Budget tracking не персистится (DESIGN)

`BudgetTracker._sessions` — in-memory dict. При перезапуске backend все бюджеты сбрасываются. Агент может превысить лимит если backend перезапустился в середине сессии.

**Severity:** DESIGN LIMITATION

### 6.11 test_ws.py полностью нерабочий — ImportError при загрузке (CRITICAL)

**Файл:** `api/tests/test_ws.py`

**ВСЕ 12 тестов** не выполняются — импорт на уровне файла (строка 9) вызывает `ImportError`:

```python
# test_ws.py:9 — ImportError: _parse_handoff_block не существует в ws.py
from app.routers.ws import _parse_handoff_block
```

`_parse_handoff_block` перенесена в orchestrator_service.py как `parse_handoff_block`. Строка 148 патчит `_stream_response`, которая также не существует (заменена на `_run_graph` в P4).

Последствия:
- **12 из 12** тестов не выполняются
- **0 тестов** для текущего LangGraph-based WebSocket handler (`_run_graph`, `Command(resume=...)`, interrupt detection)
- **0 тестов** для `graph_service.py` (подтверждено: файл `test_graph_service.py` не существует)
- **0 тестов** для `orchestrator_service.py` (подтверждено: файл `test_orchestrator_service.py` не существует)
- Регрессии в core chat flow **не детектируются**

**Severity:** CRITICAL
**Fix:** Переписать test_ws.py для текущего кода. Создать test_graph_service.py и test_orchestrator_service.py.

### 6.12 Sub-agent sessions не закрываются в БД (BUG)

**Файл:** `api/app/services/graph_service.py:114-116`

```python
if is_sub:
    await runtime.stop_session(session_id)
```

`runtime.stop_session()` убивает процесс и удаляет из `_processes` dict (runtime.py:194-198), но **не вызывает** `session_service.stop_session(db, session_id)` для обновления статуса в БД. Sub-agent сессии остаются с `status="active"` навсегда.

Проблемы:
- `get_sessions()` (session_service.py:39) фильтрует `where(Session.status == "active")` — orphaned sub-sessions загрязняют список
- Нет способа отличить реально активную сессию от orphaned sub-agent сессии

**Severity:** BUG
**Fix:** Добавить `await stop_session(db, session_id)` (из session_service) после `runtime.stop_session()` в run_agent_node для sub-agents.

### 6.13 gate_node — нет транзакционной целостности (DESIGN)

**Файл:** `api/app/services/graph_service.py:214-232`

gate_node выполняет 4 операции с side effects при одобрении handoff:

1. `create_session(db, ...)` — **коммит в БД** (session_service.py:30)
2. `add_message(db, ...)` — **коммит в БД** (session_service.py:93)
3. `runtime.start_session(...)` — изменение in-memory state
4. `ws.send_json(...)` — отправка по WebSocket

Каждый `await db.commit()` фиксируется немедленно. Если шаг 3 бросает исключение (например, `AgentRuntimeError("Session already running")`), шаги 1-2 уже закоммичены и **не откатываются**. Создаётся orphaned Session + Message в БД без запущенного runtime.

**Severity:** DESIGN
**Fix:** Обернуть шаги 1-3 в один `db.begin()` блок, или добавить compensating action (удаление session) в except.

### 6.14 AsyncSession lifetime через interrupt (DESIGN)

**Файл:** `api/app/routers/ws.py:36, 76`

`db: AsyncSession = Depends(get_db)` создаёт одну SQLAlchemy session на весь WebSocket lifecycle. Эта session передаётся через `graph_config["configurable"]["db"]` и используется во всех node-функциях.

Проблемы:
- **Identity map accumulation:** Session накапливает ORM объекты в identity map за весь lifecycle WebSocket-соединения (может быть часы)
- **Stale reads через interrupt:** Между interrupt() и resume может пройти минуты/часы. Другие процессы могут изменить данные. gate_node читает `get_agent_handoff_targets()` на stale session без refresh
- **Нет транзакционных границ:** Множественные `db.commit()` без явных `db.begin()` — каждый commit фиксируется отдельно
- **Error contamination:** Если `IntegrityError` произойдёт в одном commit, session может стать невалидной для последующих операций (зависит от autobegin)

**Severity:** DESIGN
**Fix:** Создавать новую db session для каждого `astream()` вызова вместо переиспользования одной session через interrupt.

### 6.15 Нет reconnect/resume для interrupted state (MISSING FEATURE)

**Файл:** `api/app/routers/ws.py:106`

`interrupted = False` — in-memory flag. При WebSocket disconnect и reconnect:
1. Checkpoint с interrupted state **сохраняется** в PostgreSQL (LangGraph persist)
2. При новом WS-соединении `interrupted` инициализируется `False`
3. ws.py **не проверяет** existing checkpoint при подключении
4. Пользователь не узнаёт, что граф ждёт approve/reject
5. Следующее "message" создаёт новый initial_state на том же thread_id

Frontend реконнектится автоматически (useChat.ts:258-264, до 5 попыток), но серверная сторона не восстанавливает interrupted state.

**Severity:** MISSING FEATURE (не баг — система не спроектирована для recovery)
**Fix:** При WebSocket connect проверять checkpoint на pending interrupt для данного thread_id.

### 6.16 gate_node нарушает Single Responsibility (DESIGN)

**Файл:** `api/app/services/graph_service.py:174-244`

gate_node совмещает 7 обязанностей:
1. HITL gate решение (interrupt + approve/reject)
2. Поиск target-агента (get_agent_handoff_targets + name matching)
3. Детектирование циклов (chain comparison)
4. Создание DB session для sub-агента
5. Построение system prompt (_build_agent_prompt)
6. Запуск runtime sub-агента
7. Уведомление UI (handoff_start)

Следствие: изменение любой из 7 обязанностей требует изменения gate_node, увеличивая blast radius.

**Severity:** DESIGN
**Fix:** Разделить на `gate_node` (только interrupt + решение) и `setup_sub_agent_node` (шаги 2-7).

### 6.17 MAX_DEPTH достигается молча (UX)

**Файл:** `api/app/services/graph_service.py:251-255`

```python
def route_after_agent(state: WorkflowState) -> Literal["notify_handoff", "__end__"]:
    if state.get("handoff_target") and state["depth"] < MAX_DEPTH:
        return "notify_handoff"
    return END
```

Если агент хочет сделать handoff но `depth >= MAX_DEPTH` (5), граф молча завершается через `END`. Пользователь получает `"done"` без уведомления, что handoff был проигнорирован из-за лимита глубины. Нет логирования.

**Severity:** UX
**Fix:** Отправлять WS-событие `{"type": "max_depth_reached", "attempted_target": ...}` и логировать warning.

### 6.18 Цепочка исключений при WS disconnect в run_agent_node (RELIABILITY)

**Файл:** `api/app/services/graph_service.py:95-112`

Если WebSocket disconnect происходит во время streaming в run_agent_node:
1. `ws.send_json(event)` (строка 96 или 102) бросает исключение
2. `except Exception as exc` (строка 103) ловит его
3. Error handler пытается отправить ошибку через тот же мёртвый WebSocket (строки 106-112)
4. Это бросает ещё одно исключение, которое **не ловится** внутри run_agent_node
5. Исключение пробрасывается через `graph.astream()` в `_run_graph`
6. `except WebSocketDisconnect: raise` (ws.py:188) может не сработать если тип исключения — `RuntimeError`, а не `WebSocketDisconnect`

Для sub-agents (строки 106-110 + 116-117) после ошибки отправки error ещё вызывается `runtime.stop_session()` и `ws.send_json({"type": "handoff_done"})` — третья попытка отправки в мёртвый WebSocket.

**Severity:** RELIABILITY
**Fix:** Проверять состояние WebSocket перед отправкой, или оборачивать каждый `ws.send_json()` в try/except с early return.

### 6.19 @retry на _launch_process — мёртвая логика (DESIGN)

**Файл:** `api/app/services/runtime.py:240-244`
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(TransientAgentError),
)
async def _launch_process(self, cmd, env, cwd):
    process = await asyncio.create_subprocess_exec(...)
    return process
```

`_launch_process` выполняет только `asyncio.create_subprocess_exec()`, который бросает `OSError`/`FileNotFoundError`, **не** `TransientAgentError`. `TransientAgentError` бросается в `_read_stream` (строка 317), которая вызывается **после** `_launch_process`. Retry-декоратор **никогда не сработает**.

P1 roadmap заявлял "tenacity retry, exponential backoff" как реализованное — фактически retry привязан к неправильному методу.

**Severity:** DESIGN (заявленная функциональность не работает)
**Fix:** Перенести retry на `send_message()` целиком (оборачивая весь CLI-вызов), или изменить на `retry_if_exception_type(OSError)` для subprocess creation.

### 6.20 stderr_task leak в _read_stream (RELIABILITY)

**Файл:** `api/app/services/runtime.py:290-310`
```python
stderr_task = asyncio.create_task(process.stderr.read()) if process.stderr else None
async for line in process.stdout:  # если здесь exception...
    ...
await process.wait()
if stderr_task:
    stderr = await stderr_task  # ...сюда не дойдём
```

Если исключение произойдёт в цикле `async for` (строки 292-305) до строки 310, `stderr_task` не будет await'нута. Это:
- Утечка asyncio task
- `RuntimeWarning: coroutine was never awaited` или `Task was destroyed but it is pending`

**Severity:** RELIABILITY
**Fix:** Обернуть в try/finally: `finally: if stderr_task: await stderr_task`

### 6.21 process.wait() без timeout (RELIABILITY)

**Файл:** `api/app/services/runtime.py:307`
```python
await process.wait()  # нет timeout — может ждать вечно
```

Если CLI-процесс зависнет (не завершится и перестанет писать в stdout), `process.wait()` заблокирует coroutine навсегда. В `_kill_process` timeout 5s есть, но `_read_stream` не использует `_kill_process`.

**Severity:** RELIABILITY
**Fix:** `await asyncio.wait_for(process.wait(), timeout=300)`

### 6.22 Budget не получает model name — cost estimation opus занижена 5x (ACCURACY)

**Файл:** `api/app/services/runtime.py:141-146`
```python
budget_event = self._budget.record_usage(
    session_id=str(session_id),
    input_tokens=input_tokens,
    output_tokens=output_tokens,
    reported_cost=cost_usd,
    # model= НЕ передаётся
)
```

`record_usage()` принимает `model: Optional[str] = None` (budget.py:148), но runtime не передаёт его. Если `reported_cost` из CLI отсутствует, `compute_cost` использует `DEFAULT_PRICING` ($3/$15 per 1M — sonnet-level). Для opus ($15/$75) стоимость занижена в **5x**.

**Severity:** ACCURACY
**Fix:** Добавить `model=event.get("model")` в вызов `record_usage()` или извлекать model из CLI output.

### 6.24 kill-all каскадирует в circuit breaker OPEN (RELIABILITY)

При side-by-side (2 панели):
1. Panel A: `send_message()` → kill ALL → убивает процесс Panel B
2. Panel B: `_read_stream()` получает ошибку → stderr содержит keywords → `TransientAgentError`
3. `TransientAgentError` → `circuit_breaker.record_failure()`
4. **5 таких kill-ов в пределах failure_window (60s) → CB переходит в OPEN**
5. **Обе панели заблокированы** на recovery_timeout (30s)

**Severity:** RELIABILITY (cascading failure при side-by-side)
**Fix:** Fix 6.1 (kill current only) автоматически устраняет эту проблему.

### 6.25 eval_service.execute_eval_run() — нет concurrent protection (CORRECTNESS)

**Файл:** `api/app/services/eval_service.py:127-258`

`execute_eval_run()` устанавливает `status="running"` без проверки текущего статуса. Два одновременных вызова для одного `run_id` создадут дубликаты `EvalResult` записей.

**Severity:** CORRECTNESS
**Fix:** Проверять текущий status перед execute: `if run.status != "pending": raise ...`

### 6.26 Zero React.memo — все сообщения перерисовываются (PERFORMANCE)

Во всём фронтенде **0 использований** React.memo, useMemo. ChatMessage, ToolUseBlock, HandoffBlock не мемоизированы. Каждое новое сообщение перерисовывает **ВСЕ** предыдущие сообщения и компоненты. Для длинных сессий (100+ сообщений) — реальная деградация.

useCallback используется в useChat.ts (6 callbacks) и ChatPage.tsx (3 callbacks), но **0** в ChatPanel, ChatWindow, ChatMessage.

**Severity:** PERFORMANCE
**Fix:** Добавить React.memo на ChatMessage, ToolUseBlock, HandoffBlock. Добавить useMemo для статичных данных.

### 6.27 Linear WS reconnection — thundering herd (RELIABILITY)

**Файл:** `web/src/hooks/useChat.ts`
```typescript
const RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECT_ATTEMPTS = 5;
// ...
setTimeout(connect, RECONNECT_DELAY_MS);  // фиксированный delay
```

При массовом disconnect (сеть упала) все клиенты reconnect одновременно каждые 2 секунды → thundering herd на backend.

**Severity:** RELIABILITY
**Fix:** Exponential backoff: `setTimeout(connect, RECONNECT_DELAY_MS * 2 ** reconnectCount.current)`

### 6.28 CheckConstraints рассогласованы между ORM-моделями и миграциями (DESIGN)

Несколько CHECK CONSTRAINT определены **только в миграциях**, но отсутствуют в ORM-моделях:

| Constraint | Миграция | ORM-модель | Статус |
|-----------|----------|------------|--------|
| `ck_semantic_memory_kind` IN ('adr', 'convention', 'pattern') | 003:63-66 | memory.py:32 — только комментарий | ⚠ Нет в модели |
| `ck_eval_runs_status` IN ('pending', 'running', 'completed', 'failed') | 004:62-65 | evaluation.py:45-47 — только комментарий | ⚠ Нет в модели |
| `ck_eval_results_verdict` IN ('pass', 'fail', 'error') | 004:91-94 | evaluation.py:77-79 — только комментарий | ⚠ Нет в модели |

Для сравнения: Session.status, Message.role, AgentLink.link_type **имеют** CheckConstraint в ORM-моделях.

Последствия:
- `alembic revision --autogenerate` не увидит эти constraints (они не в модели) и может потерять их при рефакторинге
- Валидация происходит только на уровне БД, а не Python — ошибки заметны поздно

**Severity:** DESIGN
**Fix:** Добавить `__table_args__` с `CheckConstraint` в `SemanticMemory`, `EvalRun`, `EvalResult`.

### 6.29 Runtime._processes не очищается при CASCADE-удалении (BUG)

При удалении Team или Agent через API каскадно удаляются Sessions из БД (`ondelete="CASCADE"`), но `runtime._processes` dict **не обновляется**. Если CLI-процесс ещё запущен — zombie process. Нет хука "при удалении агента — остановить все его runtime-процессы".

**Severity:** BUG (zombie processes при удалении)
**Fix:** В `agent_service.delete_agent()` или `team_service.delete_team()` — вызвать `runtime.stop_session()` для всех активных сессий перед удалением.

### 6.30 LangGraph checkpoints не очищаются при удалении сессий (DESIGN)

`langgraph_checkpoints` и `langgraph_writes` таблицы (создаются через `checkpointer.setup()` в main.py lifespan) используют `thread_id = str(session_id)`. При удалении Session из БД (через CASCADE или API) checkpoint'ы **не удаляются** — нет FK-связи между sessions и langgraph-таблицами.

**Severity:** DESIGN (рост данных, потенциальный конфликт при коллизии UUID)
**Fix:** Добавить cleanup checkpoints при удалении session.

### 6.31 Zombie `__streaming__` элемент при WS disconnect (UX)

**Файл:** `web/src/hooks/useChat.ts:69`

Если WebSocket disconnect происходит во время стриминга (между `assistant_text` и `done`), элемент с `id: "__streaming__"` остаётся в items навсегда. `findIndex("__streaming__")` на строке 98 будет находить его при следующем стриминге, но при reconnect `items` state не очищается от zombie-элементов.

**Severity:** UX
**Fix:** При disconnect или reconnect — удалять `__streaming__` из items, или преобразовывать в error-message.

### 6.32 Side-by-side — встроенная фича, kill-all конфликт не гипотетический (BUG)

**Файл:** `web/src/pages/ChatPage.tsx:49-62`

ChatPage создаёт два независимых `<ChatPanel>` с разными sessionId при открытии side panel. Каждый ChatPanel → useChat → WebSocket → runtime. Два runtime-соединения на один singleton `AgentRuntime()`. Kill-all в одном убивает процесс другого.

Это **не** гипотетический сценарий — ChatPage:18-24 (`handleOpenSide`) активно поддерживает dual-panel layout. Баг 6.1 проявляется в **штатной фиче UI**.

**Severity:** BUG (каскадирует через 6.1 → 6.24)

### 6.33 Миграция 003 — docstring несоответствие revision (COSMETIC)

**Файл:** `api/alembic/versions/003_add_vector_memory.py:1-16`

Docstring: `Revision ID: 002`, фактический `revision: str = "003"`. Копипаст из предыдущей миграции. Может путать при отладке миграций.

**Severity:** COSMETIC
**Fix:** Исправить docstring на `Revision ID: 003`.

### 6.34 Stale pending refs при reconnect (BUG)

**Файл:** `web/src/hooks/useChat.ts:287-294`

При WebSocket disconnect cleanup закрывает соединение, но **не сбрасывает** `pendingTextRef`, `pendingToolsRef`, `pendingSubAgentRef`. При reconnect:
1. `pendingTextRef.current` содержит текст от предыдущего стриминга
2. Новый `assistant_text` конкатенируется с ним (строка 71: `pendingTextRef.current += event.content`)
3. Пользователь видит дублированный/мусорный текст

```tsx
// useChat.ts:287-294 — cleanup
return () => {
  if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
  if (wsRef.current) {
    wsRef.current.close();
    wsRef.current = null;
  }
  // ⚠ pendingTextRef, pendingToolsRef, pendingSubAgentRef НЕ сбрасываются
};
```

**Severity:** BUG (data corruption в UI при reconnect)
**Fix:** Добавить сброс всех pending refs в cleanup и при reconnect: `pendingTextRef.current = ""; pendingToolsRef.current = []; pendingSubAgentRef.current = null;`

### 6.35 Budget events — protocol gap (PROTOCOL GAP)

**Файлы:** `api/app/services/budget.py:180-203` → `runtime.py:148` → `graph_service.py:102` → `ws.py` → `web/src/hooks/useChat.ts`

Backend отправляет 4 типа budget-событий (`budget_warning`, `budget_exceeded`, `sub_agent_budget_warning`, `sub_agent_budget_exceeded`), но:
1. `WsIncoming` тип в `web/src/types/index.ts` не включает их (13 типов, budget отсутствует)
2. `handleEvent` switch в useChat.ts не имеет case для budget-типов
3. События молча отбрасываются через `default: break`

Пользователь **не видит** предупреждений о превышении бюджета. Агент может быть убит по `budget_exceeded` без UI-уведомления.

**Severity:** PROTOCOL GAP (backend отправляет, frontend игнорирует)
**Fix:** Добавить budget-типы в `WsIncoming`, обработать в `handleEvent`, показать уведомление/banner в ChatPanel.

### 6.36 Sub-agent process orphan при WS disconnect (RESOURCE LEAK)

**Файл:** `api/app/services/graph_service.py:115-116`

Sub-agent cleanup (`runtime.stop_session(sub_session_id)`) вызывается **только** в `run_agent_node` при нормальном завершении (строки 115-116). При WS disconnect:
1. `ws.py` вызывает `runtime.kill_active_process(session_id)` — убивает **только** main session
2. Sub-agent CLI-процесс остаётся запущенным (orphan)
3. `_processes[sub_session_id]` не очищается

**Severity:** RESOURCE LEAK
**Fix:** При WS disconnect убивать все процессы, связанные с thread_id (main + sub-agent), или использовать process group.

### 6.37 `__interrupt__` detection в ws.py не верифицировано (UNKNOWN)

**Файл:** `api/app/routers/ws.py:185`

```python
if "__interrupt__" in chunk:
```

Функция `_run_graph()` проверяет наличие строки `"__interrupt__"` в chunk из `astream(stream_mode="values")`. LangGraph при `stream_mode="values"` отдаёт значения state, не события. Формат наличия `__interrupt__` в state values **не документирован** в LangGraph docs и может зависеть от версии.

**Severity:** UNKNOWN (требует эксперимента)
**Fix:** Добавить в раздел 11 (требует изучения). Написать integration test, проверяющий что interrupt корректно детектируется.

### 6.38 Approval flow и другие сценарии не покрыты тестами (TEST GAP)

**Файл:** `web/src/hooks/useChat.test.ts`

16 тестов (ранее ошибочно указывалось 14) покрывают: idle, connect, status on open, streaming, done, tool_use, sendMessage, stop, error, reconnect, no-connect-when-disabled, no-reconnect-after-stop, handoff_start, sub_agent streaming, handoff_done, handoff_cycle.

**Не покрыты (расширенный список v8):**
- `approval_required` event handling, `approveHandoff()`, `rejectHandoff()` — полный HITL approval flow
- Reconnect state preservation (pendingApproval теряется)
- Budget events (4 типа) — budget_warning, budget_exceeded, sub_agent_budget_warning, sub_agent_budget_exceeded
- `tool_result` event — привязка result к tool_use
- `sub_agent_tool_use`, `sub_agent_tool_result`, `sub_agent_error` events
- `sendMessage` при неготовом WS (error "Connection not ready")
- MAX_RECONNECT_ATTEMPTS (5) — тестируется только один reconnect
- `ws.onerror` handler и parse error на malformed message

Всего **12 непокрытых сценариев**. Approval flow — критический HITL path.

**Severity:** TEST GAP (критический path без покрытия)
**Fix:** Добавить тесты для approval flow, budget events, tool_result, sub_agent events, error edge cases.

### 6.39 tool_use и sub_agent_tool_use не вызывают setItems (UX)

**Файл:** `web/src/hooks/useChat.ts:74-80, 179-186`

Аналогично 6.2 (tool_result), обработка `tool_use` и `sub_agent_tool_use` только мутирует refs без вызова `setItems()`:

```tsx
case "tool_use":
  pendingToolsRef.current.push({ tool_name: event.tool_name, tool_input: event.tool_input });
  break;  // ← нет setItems
```

Tool-вызовы не отображаются в UI до получения `done` или `handoff_done`. При длительных tool execution (10+ секунд) пользователь не видит что агент работает.

**Severity:** UX (delayed rendering, расширение 6.2)
**Fix:** Вызывать `setItems()` с копией pending state после каждого tool_use/sub_agent_tool_use для real-time rendering.

### 6.40 memory_service: input_type="document" для query embeddings (QUALITY)

**Файл:** `api/app/services/memory_service.py:40-42`
```python
result = await asyncio.to_thread(
    client.embed, [text_input], model=EMBEDDING_MODEL, input_type="document"
)
```

Функция `_embed()` используется как для сохранения (`save_episodic`, `save_semantic`), так и для поиска (`search_memories`). Voyage AI различает `input_type="document"` и `input_type="query"` — модель оптимизирует embeddings по-разному для этих типов. Для search запросов (строка 120: `_embed(query)`) используется неправильный `input_type`, что снижает качество retrieval.

**Severity:** QUALITY (search relevance degraded)
**Fix:** Добавить параметр в `_embed()`:
```python
async def _embed(text_input: str, input_type: str = "document") -> list[float]:
    client = _get_voyage_client()
    result = await asyncio.to_thread(
        client.embed, [text_input], model=EMBEDDING_MODEL, input_type=input_type
    )
```
И вызывать `_embed(query, input_type="query")` в `search_memories`.

### 6.41 judge_service: return type annotation не соответствует реальному возвращаемому значению (TYPING)

**Файл:** `api/app/services/judge_service.py:153, 198`

Сигнатура: `async def judge_agent_output(...) -> JudgeResponse:`
Фактический return: `return response, token_usage` — tuple[JudgeResponse, dict].

Вызов в eval_service.py:191: `judge_response, token_usage = await judge_agent_output(...)` — работает в runtime, но противоречит аннотации. Type checker (mypy/pyright) пометит как ошибку.

**Severity:** TYPING
**Fix:** Изменить аннотацию на `-> tuple[JudgeResponse, dict]:`.

### 6.42 judge_service: нет retry при невалидном JSON от LLM (RELIABILITY)

**Файл:** `api/app/services/judge_service.py:111`
```python
data: dict[str, Any] = json.loads(text)
```

Если LLM вернёт невалидный JSON, `json.loads` бросит `JSONDecodeError`. Нет retry, нет fallback. Ошибка поднимется до `execute_eval_run()`, которая запишет `verdict="error"`. Judge уже потратил токены — результат отброшен без попытки переспросить.

**Severity:** RELIABILITY
**Fix:** Обернуть в retry (до 2 повторов) или fallback с просьбой вернуть валидный JSON.

### 6.43 Background eval task — status застревает на "running" при ошибке (RELIABILITY)

**Файл:** `api/app/routers/evaluations.py:75-80`
```python
async def _run_eval():
    from app.database import async_session
    async with async_session() as session:
        await eval_service.execute_eval_run(session, run.id, case_ids=case_ids)
```

Нет try/finally. Если `execute_eval_run()` бросает исключение до обновления status (например, `ValueError("No eval cases found")`), run останется со `status="running"` навсегда. Frontend будет бесконечно polling'ить этот run (useEvalRun refetchInterval: 3000 при status "running").

**Severity:** RELIABILITY
**Fix:** Обернуть в try/except с обновлением status на "failed":
```python
async def _run_eval():
    from app.database import async_session
    async with async_session() as session:
        try:
            await eval_service.execute_eval_run(session, run.id, case_ids=case_ids)
        except Exception as e:
            run_obj = await session.get(EvalRun, run.id)
            if run_obj and run_obj.status == "running":
                run_obj.status = "failed"
                await session.commit()
```

### 6.44 execute_eval_run — один commit для всех results (DURABILITY)

**Файл:** `api/app/services/eval_service.py:167-247`

Внутри цикла `for case in cases` — `db.add(eval_result)` без промежуточных `commit()`. Финальный `await db.commit()` на строке 247 коммитит все результаты атомарно. Если БД или процесс упадёт между case #5 и case #10 — все 10 результатов потеряются (и потраченные на judge LLM-токены).

**Severity:** DURABILITY (при long-running eval)
**Fix:** Добавить `await db.commit()` после каждого `db.add(eval_result)` внутри цикла, или после каждых N кейсов.

### 6.45 judge_service создаёт Anthropic client на каждый вызов (PERFORMANCE)

**Файл:** `api/app/services/judge_service.py:168`
```python
client = anthropic.AsyncAnthropic(api_key=api_key) if api_key else anthropic.AsyncAnthropic()
```

Аналогично 6.9 (Voyage client). При batch eval run из 10 кейсов создаётся 10 httpx-клиентов. Severity ниже чем 6.9 — Anthropic SDK использует `httpx.AsyncClient`, который легче sync Voyage Client.

**Severity:** PERFORMANCE (minor)
**Fix:** Module-level singleton аналогично рекомендации M6.

### 6.46 0 тестов для memory_service (TEST GAP)

Среди 13 test-файлов в `api/tests/` отсутствуют `test_memory.py` и `test_memory_service.py`. Покрытие memory-подсистемы = 0. Не протестированы:
- `_embed()` — Voyage API вызов
- `search_memories()` — merge + sort логика
- `_search_episodic()` / `_search_semantic()` — pgvector queries

**Severity:** TEST GAP

### 6.47 0 тестов для MCP server (TEST GAP)

Нет тестов в `mcp-workspace/`. Не протестированы:
- `list_tasks()`, `get_task()`, `update_task_status()` — task tools
- `list_specs()`, `get_spec()` — spec tools с path traversal protection
- `get_project_context()`, `get_protocol()` — resources

**Severity:** TEST GAP

### 6.48 Anthropic API key не в централизованном config (INCONSISTENCY)

**Файлы:** `api/app/config.py:16` vs `api/app/services/judge_service.py:168`

`voyage_api_key` определён в `config.py` с prefix `AC_`. Anthropic API key используется через `anthropic.AsyncAnthropic()` без параметра — SDK читает `ANTHROPIC_API_KEY` из env напрямую, минуя `Settings`. Нет валидации наличия ключа при старте.

**Severity:** INCONSISTENCY
**Fix:** Добавить `anthropic_api_key: str = ""` в Settings и использовать в judge_service.

### 6.49 voyage_api_key="" по умолчанию — lazy failure (CONFIG)

**Файл:** `api/app/config.py:16`
```python
voyage_api_key: str = ""
```

Если env var `AC_VOYAGE_API_KEY` не задана, `voyageai.Client(api_key="")` будет создан при первом вызове `_embed()`, и API вернёт AuthenticationError. FastAPI стартует без ошибок — failure только при запросе к memory endpoints. Аналогично для Anthropic key в judge_service.

**Severity:** CONFIG (lazy failure)
**Fix:** Валидация при startup, или хотя бы log.warning если ключи пусты.

### 6.50 useEvalRuns — безусловный polling каждые 5 секунд (PERFORMANCE)

**Файл:** `web/src/hooks/useEvaluations.ts:48`
```typescript
refetchInterval: 5000,
```

Список eval runs рефетчится каждые 5 секунд **безусловно**, даже если все runs завершены. В отличие от `useEvalRun` (строки 57-60), который polling'ит только `running`/`pending`, список не учитывает статус.

**Severity:** PERFORMANCE (wasteful network)
**Fix:** Условный polling как в `useEvalRun`:
```typescript
refetchInterval: (query) => {
  const runs = query.state.data ?? [];
  return runs.some(r => r.status === "running" || r.status === "pending") ? 5000 : false;
},
```

### 6.51 eval_service.duration_ms измеряет только agent_output, не judge (MISLEADING)

**Файл:** `api/app/services/eval_service.py:169-177`

`duration_ms` замеряет время между `start_time` и получением `agent_output` (строка 177), но **не включает** время вызова judge (строки 191-193). В `EvalResult` поле `duration_ms` хранится вместе с judge verdict — кажется что это полное время оценки кейса.

**Severity:** MISLEADING
**Fix:** Перенести `start_time` перед циклом или замерять отдельно agent_time и judge_time.

### 6.52 `anthropic` пакет не объявлен в requirements.txt (DEPENDENCY)

**Файл:** `api/app/services/judge_service.py:16` + `api/requirements.txt`

```python
import anthropic  # judge_service.py:16
```

Пакет `anthropic` используется в judge_service, но **отсутствует** в requirements.txt. Вероятно, устанавливается как транзитивная зависимость от `langgraph` (который использует `>=` pin). Если при обновлении langgraph транзитивная зависимость изменится — judge_service сломается при импорте без явной ошибки в `pip install`.

**Severity:** DEPENDENCY (скрытая зависимость)
**Fix:** Добавить `anthropic>=0.40.0` в requirements.txt.

### 6.53 web/Dockerfile не копирует package-lock.json — нерепродуцируемые билды (RELIABILITY)

**Файл:** `web/Dockerfile:5-6`
```dockerfile
COPY package.json ./
RUN npm install
```

`package-lock.json` **существует** в web/, но Dockerfile копирует только `package.json`. `npm install` без lockfile разрешает зависимости по-новому при каждом build → нерепродуцируемые билды. Разные разработчики/CI могут получить разные версии.

**Severity:** RELIABILITY (нерепродуцируемый build)
**Fix:** Добавить `COPY package-lock.json ./` и заменить `npm install` на `npm ci`.

### 6.54 requirements.txt смешивает production и test зависимости (INFRA)

**Файл:** `api/requirements.txt:10-11`
```
pytest==8.3.4
pytest-asyncio==0.25.0
```

Test-зависимости (`pytest`, `pytest-asyncio`) в одном файле с production-зависимостями. При `docker compose build` тестовые пакеты попадают в production image.

**Severity:** INFRA (minor — dev-only на данном этапе)
**Fix:** Вынести в `requirements-dev.txt` и устанавливать отдельно в dev-сценариях.

### 6.55 Непоследовательный version pinning в requirements.txt (RELIABILITY)

**Файл:** `api/requirements.txt`

Часть зависимостей пиннована строго (`fastapi==0.115.6`, `sqlalchemy==2.0.36`), часть — нестрого (`langgraph>=0.3.0`, `psycopg[binary]>=3.1`, `pgvector>=0.3.0`, `voyageai>=0.3.0`). Нестрогие зависимости могут обновиться при rebuild и сломать совместимость.

**Severity:** RELIABILITY (потенциальные breaking changes при rebuild)
**Fix:** Пиннировать все зависимости строго, использовать `pip-compile` для lock-файла.

### 6.56 Makefile — нет команд test/lint, неполный .PHONY (INFRA)

**Файл:** `Makefile`

`.PHONY: dev stop migrate logs import` — пропущены `new-migration`, `logs-api`, `db-shell`. Отсутствуют команды для запуска тестов (`make test`), линтинга (`make lint`), проверки типов. Разработчик должен вручную запускать `docker compose exec api pytest`.

**Severity:** INFRA (DX friction)
**Fix:** Добавить targets:
```makefile
test-api:
	docker compose -f docker-compose.dev.yml exec api pytest
test-web:
	docker compose -f docker-compose.dev.yml exec web npm test
lint:
	docker compose -f docker-compose.dev.yml exec web npm run lint
```

### 6.57 Весь API без аутентификации — нет модели пользователя (SECURITY)

**Файлы:** `api/app/routers/*.py`, `api/app/main.py`, `api/app/models/session.py`

Ни один HTTP endpoint и WebSocket handler не требует аутентификации пользователя. Нет `Authorization` header, нет JWT, нет auth middleware. Session-модель не имеет `user_id`/`owner_id` поля.

Последствия:
- `GET /api/sessions` — возвращает **все** сессии без фильтрации по пользователю
- `POST /api/sessions` — любой клиент может создать сессию для любого агента
- `DELETE /api/sessions/{id}` — любой клиент может удалить любую сессию
- WebSocket `ws://host/api/ws/sessions/{id}` — `await websocket.accept()` без проверки identity (ws.py:38)
- Все REST endpoints (teams, agents, sessions, eval, memory) полностью открыты

OAuth token проверяется **только** внутри `runtime.send_message()` (runtime.py:88-92) — это проверка наличия Claude API token, а не аутентификация пользователя.

**Контекст:** Система спроектирована как single-user tool в Docker-контейнере. OAuth token хранится один на всё приложение (`delete(OAuthToken)` без WHERE, auth_service.py:113). Для dev/learning — допустимо. Для multi-user — требует архитектурного redesign.

**Severity:** SECURITY (архитектурное ограничение)
**Fix:** Для multi-user: добавить User модель, auth middleware (JWT), user_id FK в Session, ownership checks в endpoints.

### 6.58 OAuth tokens в БД без шифрования (SECURITY)

**Файл:** `api/app/models/oauth_token.py:18-19`
```python
access_token: Mapped[str] = mapped_column(Text, nullable=False)
refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

Токены хранятся как plain text. Нет шифрования на уровне приложения (Fernet/AES — grep по проекту: 0 результатов). Нет column-level encryption в PostgreSQL.

**Severity:** SECURITY (LOW для Docker dev, HIGH для production)
**Fix:** `cryptography.fernet.Fernet` для шифрования access_token/refresh_token перед записью в БД.

### 6.59 Нет rate limiting ни на одном endpoint (SECURITY)

Grep по `rate.limit|RateLimiter|slowapi|throttle` — 0 результатов в `api/`. Ни один HTTP endpoint и WebSocket handler не защищён rate limiting'ом.

Наиболее уязвимые endpoints:
- `/api/auth/login` — спам OAuth-инициацией перезаписывает `_code_verifier` (6.3)
- `/api/auth/callback` — brute force authorization codes
- WebSocket — неограниченная частота сообщений
- `/api/eval/runs` (POST) — запуск eval runs без ограничений

**Severity:** SECURITY (LOW для Docker dev, MEDIUM для production)
**Fix:** Добавить `slowapi` middleware или FastAPI rate limiting dependency.

### 6.60 Нет Content-Security-Policy header (SECURITY)

**Файл:** `api/app/main.py:28-34`

Настроен только CORSMiddleware. Отсутствуют security headers:
- `Content-Security-Policy` — нет защиты от inline scripts (defense-in-depth для XSS)
- `X-Content-Type-Options` — нет `nosniff`
- `X-Frame-Options` — нет `DENY`

Frontend использует `react-markdown` v10.1.0 (safe by default — не рендерит raw HTML, блокирует `javascript:` URLs). XSS через markdown маловероятен. CSP — превентивная мера.

**Severity:** SECURITY (LOW — react-markdown safe by default, CSP для defense-in-depth)
**Fix:** Добавить security headers middleware или в nginx/reverse proxy.

### 6.61 path traversal в specs.py — startswith без separator (SECURITY)

**Файл:** `mcp-workspace/tools/specs.py:74-78`
```python
filepath = os.path.normpath(os.path.join(specs_path, filename))
if not filepath.startswith(specs_path):
    return "Error: path traversal not allowed."
```

`startswith()` — строковая операция, не path-операция. Edge case:
- `specs_path = "/workspace/process/specs"`
- Input: `"../specs_evil/secret.md"` → normpath → `"/workspace/process/specs_evil/secret.md"`
- `startswith("/workspace/process/specs")` → **TRUE** — проверка пройдена

Любая sibling-директория с именем, начинающимся на `specs`, доступна для чтения. Для сравнения: `tasks.py` (тот же MCP server) использует regex `^TASK-\d{3}$` для task_id — безопасен.

Стандартные traversal-атаки (`../../etc/passwd`) **блокируются** корректно.

**Severity:** SECURITY (MEDIUM — эксплуатируемый edge case, scope ограничен sibling-dirs)
**Fix:** Заменить `filepath.startswith(specs_path)` на `filepath.startswith(specs_path + os.sep)` или `Path(filepath).is_relative_to(Path(specs_path))` (Python 3.9+).

### 6.62 OAuth state parameter не верифицируется на callback (COSMETIC)

**Файлы:** `api/app/services/auth_service.py:49-50, 74, 88`, `api/app/routers/auth.py:36-42`, `api/app/schemas/auth.py:19-20`

`_oauth_state` генерируется при `start_oauth_login()` (строка 49), сохраняется в глобальной переменной, затем отправляется в token exchange request (строка 88: `"state": state`). Callback endpoint `AuthCodeSubmit` принимает только `code` (schemas/auth.py:19-20) — state не передаётся клиентом и не верифицируется client-side.

**Почему это НЕ security issue:**
1. `redirect_uri` = `https://platform.claude.com/oauth/code/callback` — НЕ наш endpoint. Код получается out-of-band (пользователь вручную копирует из браузера). Стандартная CSRF-атака (redirect с подставным code) неприменима.
2. PKCE `code_verifier` уже обеспечивает привязку авторизации к инициатору — RFC 7636 специально разработан для public clients без client_secret.
3. State отправляется в token exchange body — OAuth provider может верифицировать server-side.

**Severity:** COSMETIC (best practice, не реальная уязвимость в данном flow)
**Fix:** Добавить `state` в `AuthCodeSubmit` и верифицировать `state == _oauth_state` в `exchange_code()` для полноты.

### 6.63 `CLAUDE_CODE_OAUTH_TOKEN` передаётся через env subprocess (SECURITY)

**Файл:** `api/app/services/runtime.py:100`
```python
env = {**os.environ, "CLAUDE_CODE_OAUTH_TOKEN": token}
```

OAuth access token передаётся как environment variable в Claude CLI subprocess. На Linux env vars видны через `/proc/{pid}/environ` для root и владельца процесса. В Docker-контейнере (один пользователь, root) — приемлемо. При миграции на shared infrastructure (Kubernetes, multi-tenant) — потенциальная утечка токена.

**Severity:** SECURITY (LOW для Docker, MEDIUM для shared infra)
**Fix:** Для production: передавать token через tmpfile с mode 600, или через Unix socket.

### 6.64 `.env.example` не документирует security-sensitive переменные (CONFIG)

**Файл:** `.env.example`

Содержит только 4 переменные: `AC_DATABASE_URL`, `AC_CLAUDE_CLI_PATH`, `AC_WORKSPACE_PATH`, `AC_CORS_ORIGINS`. Не документированы:
- `AC_OAUTH_CLIENT_ID` — можно переопределить public client ID
- `AC_VOYAGE_API_KEY` — API key для Voyage AI embeddings
- `ANTHROPIC_API_KEY` — API key для judge_service (используется SDK напрямую, 6.48)
- `LANGFUSE_SECRET_KEY` — API key для observability

**Severity:** CONFIG (разработчик не знает о необходимости настройки)
**Fix:** Добавить секции в `.env.example` с комментариями.

### 6.65 `entrypoint.sh: git config --global --add safe.directory '*'` (SECURITY)

**Файл:** `api/entrypoint.sh:15`
```bash
git config --global --add safe.directory '*'
```

Отключает git ownership checks для **всех** директорий глобально (CVE-2022-24765 mitigation bypass). В контексте Docker-контейнера (один пользователь, root, volume-mounted workspace) — обоснованное решение, т.к. UID mismatch между хостом и контейнером вызывает git errors.

При миграции на bare-metal или shared containers — позволяет git доверять репозиториям произвольных пользователей.

**Severity:** SECURITY (LOW для Docker dev, MEDIUM для production/shared)
**Fix:** Заменить wildcard на конкретные пути: `git config --global --add safe.directory /workspace`.

### 6.66 AgentCard обходит useCreateSession — кэш sessions не инвалидируется (BUG)

**Файл:** `web/src/components/AgentCard.tsx:4, 19`
```tsx
import { createSession } from "../api/sessions";  // прямой импорт API
// ...
const session = await createSession(agent.id);     // прямой вызов без хука
```

AgentCard вызывает `createSession()` напрямую из API-слоя, минуя хук `useCreateSession` (useSessions.ts:14-22). Хук `useCreateSession` при успехе вызывает `invalidateQueries({ queryKey: SESSIONS_KEY })`, что обновляет список сессий во всех компонентах. Прямой вызов в AgentCard **не инвалидирует кэш** — после создания сессии через AgentCard, Dashboard (ActiveSessions) и SessionList не знают о новой сессии до следующего refetchInterval (10 секунд).

Для сравнения: QuickStartChat.tsx:14 корректно использует `useCreateSession()`.

**Severity:** BUG (stale UI до 10 секунд после создания сессии)
**Fix:** Заменить прямой вызов на `useCreateSession` хук, как в QuickStartChat.

### 6.67 SessionList дублирует useQuery из useSessions (CODE DUPLICATION)

**Файл:** `web/src/components/SessionList.tsx:72-76`
```tsx
const { data: sessions, isLoading } = useQuery({
  queryKey: ["sessions"],
  queryFn: getSessions,
  refetchInterval: 10_000,
});
```

Идентичный запрос в `useSessions` (hooks/useSessions.ts:6-12): тот же queryKey `["sessions"]`, та же queryFn `getSessions`, тот же `refetchInterval: 10_000`. Благодаря одинаковому queryKey, TanStack Query дедуплицирует запросы — два компонента не вызывают API дважды. Однако при изменении одного из двух мест (например, queryKey или refetchInterval) второе может разойтись.

**Severity:** CODE DUPLICATION (не баг из-за query dedup, но risk при изменениях)
**Fix:** Заменить inline useQuery на `useSessions()` из хука.

### 6.68 Ошибки delete-мутаций не показываются пользователю (UX)

**Файлы:** `web/src/pages/Dashboard.tsx:32-36`, `web/src/pages/TeamPage.tsx:38-42`
```tsx
function handleDelete(id: string) {
  if (window.confirm("Delete this team?")) {
    deleteTeam.mutate(id);  // нет onError, нет UI feedback при ошибке
  }
}
```

При ошибке удаления (сеть недоступна, 500 от API, FK constraint violation) мутация тихо проваливается — пользователь не видит ни toast, ни сообщения об ошибке. `deleteTeam.error` доступен, но не используется нигде в шаблоне. Тот же паттерн в TeamPage для `deleteAgent.mutate()` и `deleteLink.mutate()`.

Для сравнения: TeamForm и AgentForm корректно показывают `error` через props.

**Severity:** UX (silent failure на деструктивной операции)
**Fix:** Добавить onError callback с alert/toast, или отображать `deleteTeam.error` в UI.

### 6.69 useEvalRuns и useSessions — непоследовательные стратегии polling (INCONSISTENCY)

**Файлы:** `web/src/hooks/useSessions.ts:10`, `web/src/hooks/useEvaluations.ts:48, 57-60`

Три разных подхода к polling в одном проекте:
1. `useSessions`: безусловный `refetchInterval: 10_000` — поллинг даже если все сессии остановлены
2. `useEvalRuns`: безусловный `refetchInterval: 5000` — поллинг даже если все runs завершены (6.50)
3. `useEvalRun`: условный `refetchInterval: (query) => status === "running" ? 3000 : false` — правильный паттерн

`useEvalRun` демонстрирует правильный подход (условный polling), но это единственный хук его применяющий. Остальные расходуют сетевые ресурсы на бесполезные запросы.

**Severity:** INCONSISTENCY (wasteful network + inconsistent patterns)
**Fix:** Применить условный polling по примеру `useEvalRun` к `useSessions` и `useEvalRuns`.

---

## 7. AI-first критерии

### 7.1 Context Locality

Сколько файлов должен понимать AI-агент для изменения одного модуля:

| Тип изменения | Файлов | Файлы |
|--------------|--------|-------|
| Новый CRUD ресурс | 5 | model, schema, service, router, main.py |
| Изменение CRUD-сервиса | 2-3 | service, schema, тест |
| Изменение chat flow | 8+ | ws.py, graph_service, runtime, orchestrator utils, auth, budget, circuit_breaker, session_service |
| Новый тип WS-события | 6 | ws.py, graph_service, types/index.ts, useChat.ts, ChatWindow/HandoffBlock, тест |
| Новый LangGraph node | 4 | graph_service, ws.py (если новый routing), types (если новый event), тест |
| Изменение budget логики | 3 | budget.py, runtime.py, config.py |
| Новая страница frontend | 4 | page, App.tsx (route), hooks, components |

**Оценка: 6/10** — CRUD отличный (5 файлов), core плохой (8+).

### 7.2 Change Isolation

| Зона | Isolation | Risk |
|------|-----------|------|
| team_service, agent_service, session_service | Высокая | Можно менять изолированно |
| agent_link_service | Высокая | Изолирован, используется graph_service и ws.py только для чтения |
| memory_service | Высокая | Полностью автономен |
| eval_service + judge_service | Средняя | eval зависит от judge, но оба изолированы от core |
| runtime.py | Низкая | Kill-all side effect, 6 внешних зависимостей |
| graph_service.py | Низкая | Зависит от runtime, orchestrator, session_service, agent_link_service |
| ws.py | Низкая | Зависит от graph_service, runtime, orchestrator |
| useChat.ts | Низкая | 13 event types, streaming aggregation, reconnection |

**Оценка: 5/10** — 50% модулей безопасны, 50% — зоны высокого риска.

### 7.3 Dependency Transparency

Прозрачные зависимости:
- Прямые import в top-level файлов
- FastAPI Depends(get_db) — явная DI для DB sessions
- Pydantic schemas — explicit input/output contracts

Скрытые зависимости:
- `auth_service` — lazy import внутри `runtime.send_message()` (не виден в imports)
- `telemetry.get_langfuse()` — lazy import внутри runtime
- `config["configurable"]` — WebSocket и DB передаются как нетипизированный dict через LangGraph

Module-level mutable singletons (полный реестр, v4):
| Singleton | Файл | Mutable state | Проблема |
|-----------|------|---------------|----------|
| `runtime` | runtime.py:365 | _processes dict, _budget, _breaker | Не инжектится, не тестируем |
| `_compiled_graph` | graph_service.py:296 | LangGraph graph | Устанавливается в lifespan |
| `_langfuse` | telemetry.py:12 | Langfuse client | Нет cleanup при shutdown |
| `_code_verifier` | auth_service.py:21 | OAuth PKCE verifier | Race condition при параллельных login |
| `_oauth_state` | auth_service.py:22 | OAuth state | Race condition при параллельных login |
| `settings` | config.py:29 | — (immutable) | Безопасно |
| `engine` | database.py:4 | — (immutable) | Безопасно |

5 из 7 singleton'ов имеют mutable state.

**Оценка: 6/10**

### 7.4 Deterministic Behavior

Неявная "магия":
- `setattr(agent, field, value)` в agent_service.update_agent() — динамическое обновление полей
- `send_message()` убивает ВСЕ процессы при каждом вызове
- LangGraph checkpoint resume — состояние восстанавливается из БД неявно
- `--continue` флаг в CLI определяется наличием `claude_session_id`
- `_warned` flag в SessionBudget — emit warning только один раз
- `interrupted` flag в ws.py — неявная state machine

**Оценка: 6/10**

### 7.5 Observability

Что есть:
- Langfuse trace + generation в runtime.send_message (runtime.py:111-173) — записывает session_id, input, output, usage (input/output tokens), cost_usd, вызывает flush. Работает при наличии LANGFUSE_SECRET_KEY
- `logging.getLogger(__name__)` во всех сервисах (runtime, budget, circuit_breaker, telemetry)
- Budget tracking с event emission и logging (budget.py:162-196)
- Circuit breaker с logging state transitions (circuit_breaker.py:104, 112, 120-126, 147)
- Стратегические logger.warning/error/info для CLI ошибок

Что отсутствует:
- OpenTelemetry — нет вообще
- Structured logging (JSON format) — все логи через format strings
- gen_ai semantic conventions в spans
- Correlation ID / request ID между сервисами
- Вложенные spans для tool calls (один generation на весь send_message)
- Метрики latency, error rate
- Dashboard для cost per agent
- budget.record_usage не получает model name (6.22) — cost estimation неточная

**Оценка: 4/10** (Langfuse работает но минимально, logging есть но не structured, нет OTel)

### 7.6 Testability

Что есть:
- Backend тесты (pytest-asyncio) для CRUD-модулей и инфраструктуры (budget, circuit_breaker, auth, runtime)
- 19+ frontend тестов (vitest + React Testing Library)
- Хорошее покрытие edge cases в budget и circuit_breaker

Что отсутствует:
- **test_ws.py устарел** — ссылается на P3-функции (`_parse_handoff_block`, `_stream_response`), которых нет в текущем коде (см. 6.11)
- **0 тестов для graph_service.py** — core оркестрация не покрыта
- **0 тестов для orchestrator_service.py** — parse_handoff_block, format_handoff_instructions не протестированы отдельно
- **0 тестов для memory_service.py** — `_embed()`, `search_memories()`, `_search_episodic/semantic()` не покрыты. Voyage API и pgvector queries тестируются только в production
- **0 тестов для MCP server** — `mcp-workspace/` не содержит ни одного теста. `list_tasks()`, `get_task()`, `update_task_status()`, path traversal protection в `get_spec()` — всё без покрытия
- Integration tests с реальной БД (все тесты — MagicMock)
- Тесты CASCADE-удаления
- Тесты pgvector (cosine distance, embedding storage)
- Тесты LangGraph checkpoint persistence
- Тесты concurrent sessions
- Тесты WebSocket message ordering

**Оценка: 3/10** (снижена с 5/10: тесты core chat flow не работают, graph_service/orchestrator не покрыты, 0 тестов для memory и MCP)

### 7.7 Agent Entrypoints

CLAUDE.md описывает паттерн добавления нового endpoint (5 шагов). Не описано:
- Как добавить новый тип WebSocket события
- Как добавить новый node в LangGraph
- Как добавить новую страницу на фронтенде
- Как добавить новый тип памяти
- Какие файлы являются danger zones

**Оценка: 5/10**

---

## 8. AI-agent паттерны

### 8.1 Module Boundary Architecture: 6/10

CRUD-модули имеют чёткие границы (model → schema → service → router). Core-модули (runtime, graph, ws) — нет.

Отсутствует:
- Interface/Protocol для сервисов (Python ABC)
- Явный dependency injection (кроме get_db)
- Service contracts (что принимает, что возвращает, какие exceptions)
- WorkflowState field contracts (какие поля каждый node читает/пишет)

### 8.2 Explicit System Map: 3/10

Есть:
- CLAUDE.md — структура директорий и конвенции
- learning_roadmap.md — intent и эволюция (P1-P8)

Нет:
- ARCHITECTURE.md с картой модулей и зависимостей
- WebSocket protocol specification
- LangGraph workflow diagram
- Handoff lifecycle documentation
- Dependency graph между сервисами

### 8.3 Agent-Oriented Codebase: 5/10

Есть:
- CLAUDE.md с конвенциями кода
- Naming conventions для backend и frontend
- API-конвенции "как добавить endpoint"

Нет:
- CONTRIBUTING.md / AGENT_RULES.md
- DANGER_ZONES.md (файлы с высоким blast radius)
- Pre-commit checks для автоматической валидации
- Чеклиста "что проверить после изменения модуля X"

---

## 9. Рекомендации

### 9.1 Быстрые исправления (< 1 часа)

**F1. Исправить kill-all в runtime.send_message()**

Файл: `api/app/services/runtime.py:84-86`

Заменить:
```python
for r in self._processes.values():
    await self._kill_process(r)
```
На:
```python
running = self._processes.get(session_id)
if running:
    await self._kill_process(running)
```

**F2. Исправить useChat tool_result re-render**

Файл: `web/src/hooks/useChat.ts:82-87`

Добавить `setItems()` после мутации ref для trigger re-render.

**F3. Добавить pool_pre_ping**

Файл: `api/app/database.py`
```python
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
```

**F4. React Error Boundary**

Добавить Error Boundary компонент и обернуть ChatWindow.

**F5. Исправить @retry на _launch_process**

Файл: `api/app/services/runtime.py:240-244`

Вариант A — перенести retry на send_message (обернуть весь CLI-вызов).
Вариант B — изменить retry_if_exception_type на OSError для subprocess creation.

**F6. try/finally для stderr_task**

Файл: `api/app/services/runtime.py:290-310`

Обернуть `async for` в try/finally, await stderr_task в finally.

**F7. Timeout на process.wait()**

Файл: `api/app/services/runtime.py:307`
```python
await asyncio.wait_for(process.wait(), timeout=300)
```

**F8. Передать model в budget.record_usage()**

Файл: `api/app/services/runtime.py:141`

Добавить `model=event.get("model")` в вызов record_usage().

**F9. Исправить input_type в memory_service._embed()**

Файл: `api/app/services/memory_service.py:38-42`

Добавить параметр `input_type: str = "document"` в `_embed()`, вызывать `_embed(query, input_type="query")` в `search_memories()`.

**F10. Исправить return type annotation в judge_service**

Файл: `api/app/services/judge_service.py:153`

Изменить `-> JudgeResponse:` на `-> tuple[JudgeResponse, dict]:`.

**F11. Добавить error handling в background eval task**

Файл: `api/app/routers/evaluations.py:75-80`

Обернуть `_run_eval()` в try/except с обновлением status на "failed" при ошибке.

**F12. Условный polling в useEvalRuns**

Файл: `web/src/hooks/useEvaluations.ts:48`

Заменить `refetchInterval: 5000` на условный polling как в `useEvalRun` (только при наличии running/pending runs).

**F13. AgentCard — использовать useCreateSession вместо прямого API-вызова**

Файл: `web/src/components/AgentCard.tsx:4, 16-24`

Заменить `import { createSession } from "../api/sessions"` + `await createSession(agent.id)` на хук `useCreateSession()` из `useSessions.ts`. Это исправит cache invalidation (6.66).

**F14. SessionList — использовать useSessions() вместо inline useQuery**

Файл: `web/src/components/SessionList.tsx:72-76`

Заменить inline `useQuery({ queryKey: ["sessions"], queryFn: getSessions, refetchInterval: 10_000 })` на `useSessions()` из хука (6.67).

**F15. Показать ошибки delete-мутаций**

Файлы: `web/src/pages/Dashboard.tsx:32-36`, `web/src/pages/TeamPage.tsx:38-42`

Добавить `onError: (err) => alert(err.message)` в `deleteTeam.mutate()` / `deleteAgent.mutate()`, или отображать `.error` в UI (6.68).

### 9.2 Средние улучшения (2-8 часов)

**M1. Создать ARCHITECTURE.md**

Содержание:
- Карта модулей (из секции 2 этого документа)
- WebSocket protocol (из секции 4.5)
- WorkflowState contracts (какие поля каждый node читает/пишет)
- Dependency graph между сервисами
- Danger zones

**M2. Удалить мёртвый код + вынести утилиты**

1. Создать `api/app/services/utils/handoff.py`
2. Переместить `format_handoff_instructions()`, `parse_handoff_block()` и `_build_agent_prompt()` туда (убрать underscore prefix у _build_agent_prompt — она используется cross-module)
3. Удалить `handle_handoff()` из orchestrator_service.py (129 строк мёртвого кода)
4. Удалить `run_task()` из runtime.py (30 строк мёртвого кода P3)
5. Обновить imports в graph_service.py и ws.py

**M3. Декомпозировать runtime.py (366 → 4 модуля)**

```
services/runtime/
  __init__.py          — re-export AgentRuntime, runtime
  process_manager.py   — RunningProcess, _kill_process, _launch_process (~80 строк)
  cli_builder.py       — _build_command (~30 строк)
  event_parser.py      — _read_stream, _parse_event (~80 строк)
  agent_runner.py      — send_message, run_task, start/stop (~180 строк)
```

**M4. Декомпозировать useChat.ts (338 → 4 модуля)**

```
hooks/chat/
  useChat.ts           — публичный API хука (~60 строк)
  useChatSocket.ts     — WebSocket connection + reconnect (~80 строк)
  chatEventHandler.ts  — handleEvent switch (13 cases) (~120 строк)
  chatReducer.ts       — state management для items, status (~80 строк)
```

**M5. Добавить индексы на AgentLink.from/to_agent_id**

Alembic миграция:
```python
op.create_index("idx_agent_links_from_agent_id", "agent_links", ["from_agent_id"])
op.create_index("idx_agent_links_to_agent_id", "agent_links", ["to_agent_id"])
```

**M6. Singleton для Voyage AI client**

```python
_voyage_client: Optional[voyageai.Client] = None

def _get_voyage_client() -> voyageai.Client:
    global _voyage_client
    if _voyage_client is None:
        _voyage_client = voyageai.Client(api_key=settings.voyage_api_key)
    return _voyage_client
```

**M7. Добавить CheckConstraint в ORM-модели**

Добавить CheckConstraint в ORM-модели SemanticMemory, EvalRun, EvalResult (см. 6.28).

**M8. React.memo на chat-компоненты**

Обернуть ChatMessage, ToolUseBlock, HandoffBlock в React.memo. Каждое новое сообщение сейчас перерисовывает ВСЕ предыдущие.

**M9. Exponential backoff для WS reconnection**

Файл: `web/src/hooks/useChat.ts`
```typescript
setTimeout(connect, RECONNECT_DELAY_MS * Math.pow(2, reconnectCount.current));
```

**M11. Singleton для Anthropic client в judge_service**

Аналогично M6 для Voyage. Создать module-level singleton `_anthropic_client`.

**M12. Промежуточные commit в execute_eval_run**

Файл: `api/app/services/eval_service.py:167-247`

Добавить `await db.commit()` после каждого `db.add(eval_result)` для durability при long-running eval.

**M13. Retry при невалидном JSON от LLM в judge_service**

Файл: `api/app/services/judge_service.py:111`

Обернуть `json.loads` в retry (до 2 повторов) с инструкцией LLM вернуть валидный JSON.

**M14. Startup-валидация API keys**

Файл: `api/app/config.py`

Добавить `anthropic_api_key: str = ""` в Settings. При startup — log.warning если voyage_api_key или anthropic_api_key пусты.

**M10. Lifespan retry**

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=10))
async def _setup_checkpointer(postgres_url):
    async with AsyncPostgresSaver.from_conn_string(postgres_url) as cp:
        await cp.setup()
        return cp
```

### 9.3 Архитектурные улучшения (1-2 дня)

**A1. Integration tests с testcontainers**

PostgreSQL + pgvector в Docker контейнере. Тестировать:
- Реальные SQL запросы
- CASCADE удаление
- Unique constraint violations
- pgvector cosine distance
- Transaction rollback при ошибках

**A2. Dependency injection для core services**

```python
# В main.py lifespan:
app.state.runtime = AgentRuntime(budget=BudgetTracker(), breaker=CircuitBreaker())

# В router:
def get_runtime(request: Request) -> AgentRuntime:
    return request.app.state.runtime
```

Убрать module-level singleton `runtime = AgentRuntime()`.

**A3. Типизация config["configurable"]**

```python
class GraphConfigurable(TypedDict):
    thread_id: str
    websocket: WebSocket
    db: AsyncSession
```

**A4. Structured logging**

```python
import structlog
logger = structlog.get_logger()

# В каждом сервисе:
logger.info("agent.message.sent", session_id=session_id, tokens=usage.input_tokens)
```

---

## 10. Приоритетный список улучшений

### P0 — Критические баги и сломанные тесты

| # | Что | Файл | Effort |
|---|-----|------|--------|
| 1 | **Переписать test_ws.py** для текущего LangGraph-кода | test_ws.py | 4 часа |
| 2 | **Создать test_graph_service.py** (nodes, routing, interrupt) | tests/ | 4 часа |
| 3 | Sub-agent sessions не закрываются в БД → добавить stop_session | graph_service.py:116 | 15 мин |
| 4 | kill-all → kill current session only | runtime.py:84-86 | 15 мин |
| 5 | pool_pre_ping=True | database.py | 5 мин |
| 5a | **Исправить @retry на _launch_process** (мёртвая логика) | runtime.py:240-244 | 15 мин |
| 5b | **try/finally для stderr_task** (task leak) | runtime.py:290-310 | 10 мин |
| 5c | **Timeout на process.wait()** | runtime.py:307 | 5 мин |
| 5d | **Передать model в budget.record_usage()** (cost opus 5x) | runtime.py:141 | 10 мин |
| 5e | **Сброс pending refs при reconnect** (stale data BUG) | useChat.ts:287-294 | 10 мин |
| 5f | **Kill sub-agent process при WS disconnect** (orphan leak) | graph_service.py / ws.py | 30 мин |
| 5g | **Fix input_type="document" для query embeddings** (quality) | memory_service.py:40-42 | 10 мин |
| 5h | **Fix judge return type annotation** (typing) | judge_service.py:153 | 5 мин |
| 5i | **Error handling в background eval task** (stuck status) | evaluations.py:75-80 | 15 мин |
| 5j | **Fix path traversal startswith edge case** | mcp-workspace/tools/specs.py:77 | 5 мин |
| 5k | **safe.directory: wildcard → конкретный путь** | api/entrypoint.sh:15 | 5 мин |

### P1 — Критично для AI-agent разработки

| # | Что | Effort |
|---|-----|--------|
| 6 | Создать test_orchestrator_service.py | 2 часа |
| 7 | ARCHITECTURE.md (карта + WS protocol + contracts) | 4 часа |
| 8 | React Error Boundary | 1 час |
| 9 | Удалить мёртвый код: handle_handoff() (129 строк) + run_task() (30 строк) | 1 час |
| 10 | Fix WS disconnect exception chain в run_agent_node | 1 час |
| 11 | DANGER_ZONES.md | 1 час |
| 11a | **Budget events → WsIncoming + handleEvent + UI banner** | 2 часа |
| 11b | **Тесты approval flow** (approve/reject/reconnect) | 2 часа |
| 11c | **Тесты memory_service** (_embed, search_memories, pgvector queries) | 3 часа |
| 11d | **Тесты MCP server** (tasks, specs, path traversal) | 2 часа |
| 11e | **Anthropic API key в централизованный config** | 30 мин |
| 11f | **Rate limiting на auth endpoints** (slowapi) | 2 часа |
| 11g | **Документировать security-sensitive env vars** в .env.example | 30 мин |
| 11h | **Security headers (CSP, X-Content-Type-Options, X-Frame-Options)** | 1 час |

### P2 — Значительно улучшает AI-readiness

| # | Что | Effort |
|---|-----|--------|
| 12 | Разделить gate_node → gate + setup_sub_agent | 2 часа |
| 13 | Декомпозиция runtime.py → 4 модуля | 4 часа |
| 14 | Декомпозиция useChat.ts → 4 модуля | 4 часа |
| 15 | tool_result/sub_agent_tool_result: добавить setItems для real-time rendering | 30 мин |
| 16 | Индексы на AgentLink.from/to_agent_id | 15 мин |
| 17 | Singleton Voyage AI client | 30 мин |
| 18 | Lifespan retry | 1 час |
| 19 | Уведомление при MAX_DEPTH (вместо молчаливого END) | 30 мин |
| 19a | CheckConstraints в ORM-модели (6.28) | 30 мин |
| 19b | **React.memo на ChatMessage, ToolUseBlock, HandoffBlock** | 30 мин |
| 19c | **Exponential backoff для WS reconnection** | 15 мин |
| 19d | **Concurrent protection в execute_eval_run()** | 15 мин |
| 19e | **Singleton Anthropic client в judge_service** | 15 мин |
| 19f | **Условный polling в useEvalRuns** (wasteful 5s) | 10 мин |
| 19g | **Промежуточные commit в execute_eval_run** (durability) | 30 мин |
| 19h | **Retry при невалидном JSON от LLM в judge** | 30 мин |
| 19i | **Startup-валидация API keys** (lazy failure) | 30 мин |
| 19j | **Fix duration_ms — включить judge time** (misleading) | 15 мин |
| 19k | **AgentCard → useCreateSession** (cache invalidation bug) | 10 мин |
| 19l | **SessionList → useSessions()** (code duplication) | 5 мин |
| 19m | **Показать ошибки delete-мутаций** (silent failure) | 15 мин |
| 19n | **Условный polling в useSessions** (wasteful 10s) | 10 мин |

### P3 — Масштабируемость

| # | Что | Effort |
|---|-----|--------|
| 20 | Транзакционная целостность в gate_node | 2 часа |
| 21 | Новая db session per astream() вместо shared через interrupt | 2 часа |
| 22 | Integration tests (testcontainers) | 1-2 дня |
| 23 | DI для core services | 4 часа |
| 24 | Типизация config["configurable"] (GraphConfigurable TypedDict) | 1 час |
| 25 | Structured logging | 4 часа |
| 26 | Reconnect resume для interrupted state | 4 часа |
| 27 | **WebSocket аутентификация** (token/session validation при connect) | 4 часа |
| 28 | **Шифрование OAuth tokens at-rest** (Fernet) | 2 часа |
| 29 | **User модель + ownership checks** (для multi-user) | 1-2 дня |

---

## 11. Требует дополнительного изучения

1. **pgvector performance** — нет бенчмарков при текущих данных. HNSW index настроен в миграции 003 (m=16, ef_construction=64). Нужен EXPLAIN ANALYZE для cosine_distance при 1000+ записей для проверки что индекс используется
2. **LangGraph checkpoint размер** — как быстро растёт таблица при активном использовании?
3. **Claude CLI subprocess lifecycle** — что происходит при OOM, zombie processes?
4. **entrypoint.sh `git config --global --add safe.directory *`** — security implications в production
5. **Budget при restart** — бюджеты сбрасываются при перезапуске backend, агент может превысить лимит
6. **useChat initialization race** — `enabled` параметр в useQuery защищает от race при initial load, но `refetch` (invalidateQueries) может перезаписать `items` во время активного стриминга. Вероятность низкая (refetch редко вызывается во время стриминга), но механизм защиты отсутствует
7. **Concurrent WebSocket sessions** — проверить поведение при 5+ одновременных сессиях
8. **LangGraph recursion_limit vs interrupt** — считает ли LangGraph interrupt+resume как 1 или 2 node executions? При MAX_DEPTH=5 и recursion_limit=20: если 1 → 16 executions (запас 4), если 2 → 21 executions (превышение). Нужен эксперимент
9. **Реально ли запускаются тесты?** — test_ws.py ссылается на несуществующие функции, что должно вызывать ImportError. Нужно запустить `pytest api/tests/test_ws.py -v` и проверить результат
10. **AsyncSession memory leak** — накапливает ли identity map объекты за время долгого WebSocket соединения? Нужен профайлинг при длительных сессиях
11. **Повторный astream() на тот же thread_id** — что происходит с existing checkpoint когда ws.py отправляет новый initial_state после отклонённого handoff? Перезаписывается ли checkpoint?
12. **`__interrupt__` detection format** — ws.py:185 проверяет `"__interrupt__" in chunk` при `stream_mode="values"`. Формат interrupt в state values не документирован в LangGraph. Нужен эксперимент: `async for chunk in graph.astream(...)` с interrupt → проверить формат chunk
13. **Stale refs при reconnect** — воспроизвести баг: начать стриминг → разорвать WS → reconnect → отправить новое сообщение → проверить что pendingTextRef содержит мусор от предыдущего стриминга
14. **Voyage AI input_type impact** — насколько значительно влияет использование `input_type="document"` вместо `"query"` на качество retrieval? Создать бенчмарк: 100 memories, 20 queries, сравнить recall@5 с document vs query
15. **Background eval task failure modes** — запустить eval run → убить процесс → проверить что status застрял на "running". Проверить есть ли timeout/watchdog для зависших eval runs
16. **Voyage client thread-safety** — `_embed()` вызывает `asyncio.to_thread(client.embed, ...)`. Если client — sync object, безопасен ли он для concurrent использования из разных threads? Или нужен thread-local client?
17. **OAuth provider state verification** — отправляется ли state в token exchange body (`"state": state` в auth_service.py:88) и верифицируется ли server-side Anthropic OAuth provider? Проверить: отправить token exchange request с некорректным state, проверить что provider отклоняет
18. **WebSocket session enumeration** — UUID v4 (122 бита энтропии) де-факто неугадываемы. Но утечка session_id через логи, network sniffing, browser history может дать полный доступ. Проверить: нет ли session_id в HTTP response headers, error messages, или frontend URLs
19. **prompt injection в workspace файлах** — агент читает файлы workspace через Claude CLI. Вредоносный контент в workspace-файлах (indirect prompt injection) может перехватить управление агентом. Оценить: насколько реальна угроза для internal tool vs external-facing deployment

---

*Версия 10.0 (cleaned). Десятипроходный анализ: первичный, коррекция, ревизия оркестрации, самопроверка, ревью data layer + миграции, Chat/WebSocket pipeline, Memory/Eval/MCP, тесты и инфраструктура, безопасность, Frontend CRUD/State Management. Все находки интегрированы в секции 1-11. Общее число проблем: 67.*
