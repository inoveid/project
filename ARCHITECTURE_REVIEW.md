# Архитектурный анализ Agent Console: AI-first разработка

**Дата:** 2026-03-08
**Версия:** 2.0 (после критической ревизии)
**Метод:** Двухпроходный анализ с верификацией каждого утверждения по коду

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
12. [Ошибки первого прохода анализа](#12-ошибки-первого-прохода-анализа)

---

## 1. Краткая оценка

**Проект:** Agent Console — web-приложение для управления AI-агентами.
**Стек:** Python FastAPI (backend) + React TypeScript (frontend) + PostgreSQL + pgvector.
**Размер:** ~13,000 строк кода (7,330 Python + 5,727 TypeScript), 120+ файлов.
**Зрелость:** Прошёл все 8 этапов роадмапа (P1-P8), включая LangGraph оркестрацию, vector memory, evaluation framework, circuit breaker, budget control.

| Критерий | Оценка | Комментарий |
|----------|--------|-------------|
| Структура директорий | 8/10 | Чёткое разделение api/web, слоёная архитектура |
| Модульность | 6/10 | CRUD-модули хороши; runtime (366), graph_service (303) — монолиты |
| Типизация | 9/10 | TypeScript strict, Pydantic v2, SQLAlchemy Mapped |
| Тестовое покрытие | 5/10 | 146 backend + 19 frontend тестов, но 100% mock-based, 0 integration |
| Документация | 6/10 | Хороший CLAUDE.md, но нет ARCHITECTURE.md, WS protocol, state contracts |
| AI-agent readiness | 6/10 | Конвенции описаны, нет explicit contracts между модулями |
| Observability | 4/10 | Langfuse — заглушка (25 строк), нет structured logging |
| Change isolation | 5/10 | CRUD изолированы; core services сильно связаны, kill-all ломает параллельные сессии |
| **Общая оценка** | **5.5/10** | Хорошая база для CRUD, требует доработки для AI-agent разработки |

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
│  │ChatPanel │────→│useChat (338) │──── WebSocket ─────┼──┐      │
│  │ChatWindow│     │  8 refs      │                    │  │      │
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
│  │ws.py (195)  │────────→│graph_service (303)            │      │
│  │  WS handler │         │  ├─ run_agent_node            │      │
│  │  interrupted│         │  ├─ notify_handoff_node       │      │
│  │  state flag │         │  ├─ gate_node (HITL)          │      │
│  └─────────────┘         │  └─ route_after_*             │      │
│                          │         │                     │      │
│                          │         ▼                     │      │
│                          │  runtime (366) ⚠ KILLS ALL   │      │
│                          │  ├─ budget (208)              │      │
│                          │  ├─ circuit_breaker (151)     │      │
│                          │  ├─ telemetry (25)            │      │
│                          │  └─ auth_service (lazy)       │      │
│                          │                               │      │
│                          │  orchestrator (203)           │      │
│                          │  ├─ parse_handoff_block ✓USED │      │
│                          │  ├─ _build_agent_prompt ✓USED │      │
│                          │  └─ handle_handoff ✗DEAD CODE │      │
│                          └──────────────────────────────┘      │
│                                        │                        │
│  ┌──────────────────┐                  │                        │
│  │Models (8 ORM)    │←─── SQLAlchemy ──┘                        │
│  │Schemas (Pydantic)│                                           │
│  └────────┬─────────┘                                           │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐  ┌────────────────┐                      │
│  │PostgreSQL+pgvector│  │LangGraph       │                      │
│  │ 8 таблиц         │  │Checkpoints (PG)│                      │
│  │ ⚠ Нет индексов FK│  └────────────────┘                      │
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
| runtime.py | 366 | 3 | 12 | CLI subprocess lifecycle, retry, budget, circuit breaker |
| eval_service.py | 311 | 0 | 14 | EvalCase/EvalRun CRUD, batch execution, comparison |
| graph_service.py | 303 | 0 | 6 | LangGraph StateGraph, 4 nodes, checkpoint, HITL |
| auth_service.py | 209 | 2 exc | 7 | OAuth2 PKCE, token refresh, ⚠ global state |
| budget.py | 208 | 4 | 5 | BudgetTracker, cost computation, warning/critical events |
| orchestrator_service.py | 203 | 0 | 4 | ⚠ 128 строк мёртвого кода + 2 утилиты |
| memory_service.py | 199 | 1 dc | 6 | pgvector RAG, Voyage AI embeddings |
| judge_service.py | 198 | 0 | 3 | LLM-as-Judge via Anthropic SDK |
| circuit_breaker.py | 151 | 2 | 8 | CLOSED/OPEN/HALF_OPEN state machine |
| team_service.py | 107 | 2 exc | 6 | Team CRUD |
| agent_link_service.py | 104 | 3 exc | 7 | AgentLink CRUD + routing |
| agent_service.py | 104 | 3 exc | 7 | Agent CRUD |
| session_service.py | 95 | 2 exc | 6 | Session + Message CRUD |
| telemetry.py | 25 | 0 | 1 | Langfuse singleton (заглушка) |

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

#### Models (8 ORM, ~370 строк) & Schemas (Pydantic, ~300 строк)

Standard Create/Update/Read pattern, Pydantic v2, from_attributes=True.

#### Tests (13 файлов, 146 test functions)

100% mock-based. Нет integration tests.

### Frontend (TypeScript) — 5,727 строк

| Категория | Файлов | Строк | Ключевые файлы |
|-----------|--------|-------|----------------|
| Pages | 4 | 487 | Dashboard(141), TeamPage(172), ChatPage(66), EvalDashboard(108) |
| Hooks | 9 | 734 | useChat(338), useEvaluations(88), useAgents(61) |
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
| approval_required | HITL gate: нужно одобрение | { type, from_agent, to_agent, message } |
| handoff_start | Начало handoff к sub-agent | { type, from_agent, to_agent } |
| sub_agent_assistant_text | Streaming от sub-agent | { type, content, agent_name } |
| sub_agent_tool_use | Sub-agent вызвал инструмент | { type, tool_name, tool_input } |
| sub_agent_tool_result | Результат инструмента sub-agent | { type, content } |
| sub_agent_error | Ошибка sub-agent | { type, error } |
| handoff_done | Handoff завершён | { type } |
| handoff_cycle_detected | Обнаружен цикл handoff | { type, chain } |

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
| P1 | AgentRuntime refactor | runtime.py: tenacity retry, exponential backoff, TransientAgentError | Done | Backpressure для pipes не реализован |
| P2 | Observability | telemetry.py + budget.py: Langfuse trace/span, token pricing | Partial | gen_ai semantic conventions неполные, structured logging отсутствует |
| P3 | Automatic Orchestrator | orchestrator_service.py: parse_handoff_block, auto-routing | Replaced | Заменён P4 (LangGraph). handle_handoff() = мёртвый код |
| P4 | LangGraph Redesign | graph_service.py: StateGraph, PostgreSQL checkpointing, interrupt() | Done | Time-travel debugging UI не реализован |
| P5 | Vector Memory | memory_service.py: pgvector, Voyage AI, episodic + semantic | Done | Hybrid search (BM25 + dense) — нет, только dense |
| P6 | Evaluation Framework | eval_service.py + judge_service.py + golden dataset | Done | Trajectory evaluation не реализована (только outcome) |
| P7 | MCP Server | mcp-workspace/: tasks, specs tools | Done | Полнофункционален |
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

**Severity:** BUG
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

Мутация ref без вызова `setItems()`. Результат tool_result не отображается в UI до следующего re-render по другой причине (следующий assistant_text или done).

**Severity:** BUG
**Fix:** Добавить `setItems()` после мутации.

### 6.3 auth_service — глобальное состояние (RISK)

**Файл:** `api/app/services/auth_service.py:21-22`
```python
_code_verifier: Optional[str] = None
_oauth_state: Optional[str] = None
```

Module-level переменные. Два одновременных вызова `start_oauth_login()` перезапишут друг друга. Также `get_current_access_token()` вызывается из runtime.py при каждом send_message — при параллельных сессиях возможен race condition на token refresh.

**Severity:** RISK (проявляется при параллельных сессиях)

### 6.4 orchestrator handle_handoff() — мёртвый код (DEBT)

**Файл:** `api/app/services/orchestrator_service.py:57-185`

128 строк рекурсивной оркестрации, 0 вызовов в текущем коде. Заменён LangGraph (P4). Используются только 2 утилитные функции: `parse_handoff_block()` и `_build_agent_prompt()`.

**Severity:** TECH DEBT
**Fix:** Вынести утилиты в `utils/handoff.py`, удалить handle_handoff().

### 6.5 Нет индексов на FK-колонках (PERFORMANCE)

PostgreSQL НЕ создаёт индексы для FOREIGN KEY автоматически. Отсутствуют индексы на:
- `Agent.team_id`
- `Session.agent_id`
- `Message.session_id`
- `EpisodicMemory.team_id`, `SemanticMemory.team_id`
- `EvalResult.run_id`, `EvalResult.case_id`

**Severity:** PERFORMANCE (при росте данных)
**Fix:** Alembic миграция с `op.create_index()`.

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
- `runtime = AgentRuntime()` — module-level singleton, не инжектится
- `_compiled_graph` — module-level singleton, устанавливается в lifespan

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
- Langfuse trace/span в runtime (опционально, если LANGFUSE_SECRET_KEY)
- Budget tracking с event emission (warning/critical)
- Circuit breaker с logging state transitions

Что отсутствует:
- Structured logging (ни один сервис не использует logger для бизнес-событий)
- Correlation ID / request ID
- gen_ai semantic conventions в spans
- Логирование ошибок в WebSocket (отправляются клиенту, не логируются)
- Метрики latency, error rate
- Dashboard для cost per agent

**Оценка: 4/10**

### 7.6 Testability

Что есть:
- 146 backend тестов (pytest-asyncio)
- 19+ frontend тестов (vitest + React Testing Library)
- Mock-based тестирование всех роутеров и сервисов
- Хорошее покрытие edge cases в budget и circuit_breaker

Что отсутствует:
- Integration tests с реальной БД (все тесты — MagicMock)
- Тесты CASCADE-удаления
- Тесты pgvector (cosine distance, embedding storage)
- Тесты LangGraph checkpoint persistence
- Тесты concurrent sessions
- Тесты WebSocket message ordering (mock-based)

**Оценка: 5/10**

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
2. Переместить `parse_handoff_block()` и `_build_agent_prompt()` туда
3. Удалить `handle_handoff()` из orchestrator_service.py
4. Обновить imports в graph_service.py

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

**M5. Добавить индексы на FK-колонки**

Alembic миграция:
```python
op.create_index("ix_agents_team_id", "agents", ["team_id"])
op.create_index("ix_sessions_agent_id", "sessions", ["agent_id"])
op.create_index("ix_messages_session_id", "messages", ["session_id"])
op.create_index("ix_episodic_memory_team_id", "episodic_memory", ["team_id"])
op.create_index("ix_semantic_memory_team_id", "semantic_memory", ["team_id"])
op.create_index("ix_eval_results_run_id", "eval_results", ["run_id"])
op.create_index("ix_eval_results_case_id", "eval_results", ["case_id"])
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

**M7. Lifespan retry**

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

### P0 — Баги (исправить немедленно)

| # | Что | Файл | Effort |
|---|-----|------|--------|
| 1 | kill-all → kill current session only | runtime.py:84-86 | 15 мин |
| 2 | tool_result не вызывает re-render | useChat.ts:82-87 | 15 мин |
| 3 | pool_pre_ping=True | database.py | 5 мин |

### P1 — Критично для AI-agent разработки

| # | Что | Effort |
|---|-----|--------|
| 4 | ARCHITECTURE.md (карта + WS protocol + contracts) | 4 часа |
| 5 | React Error Boundary | 1 час |
| 6 | Удалить мёртвый код handle_handoff() | 1 час |
| 7 | DANGER_ZONES.md | 1 час |

### P2 — Значительно улучшает AI-readiness

| # | Что | Effort |
|---|-----|--------|
| 8 | Декомпозиция runtime.py → 4 модуля | 4 часа |
| 9 | Декомпозиция useChat.ts → 4 модуля | 4 часа |
| 10 | Индексы на FK-колонки (миграция) | 1 час |
| 11 | Singleton Voyage AI client | 30 мин |
| 12 | Lifespan retry | 1 час |

### P3 — Масштабируемость

| # | Что | Effort |
|---|-----|--------|
| 13 | Integration tests (testcontainers) | 1-2 дня |
| 14 | DI для core services | 4 часа |
| 15 | Типизация config["configurable"] | 1 час |
| 16 | Structured logging | 4 часа |

---

## 11. Требует дополнительного изучения

1. **pgvector performance** — нет бенчмарков при текущих данных. HNSW index настроен?
2. **LangGraph checkpoint размер** — как быстро растёт таблица при активном использовании?
3. **Claude CLI subprocess lifecycle** — что происходит при OOM, zombie processes?
4. **entrypoint.sh `git config --global --add safe.directory *`** — security implications в production
5. **Budget при restart** — бюджеты сбрасываются при перезапуске backend, агент может превысить лимит
6. **useChat initialization race** — если messages загружаются после первого рендера, UI может показать пустой чат
7. **Concurrent WebSocket sessions** — проверить поведение при 5+ одновременных сессиях

---

## 12. Ошибки первого прохода анализа

Документировано для прозрачности и предотвращения повторения:

| # | Ошибка | Заявлено | Реально | Влияние |
|---|--------|----------|---------|---------|
| 1 | graph_service размер | "150+ строк" | 303 строки | Занижена сложность на 50% |
| 2 | eval_service размер | "150+ строк" | 311 строк | Занижена сложность на 52% |
| 3 | judge_service размер | "100+ строк" | 198 строк | Занижена сложность на 49% |
| 4 | useChat useState | "7 useState" | 4 useState | Завышено на 75% |
| 5 | useChat useRef | "11 refs" | 8 refs | Завышено на 37% |
| 6 | useChat events | "14 типов" | 13 типов | Завышено на 1 |
| 7 | Observability после коррекции | "6/10" | 4/10 | Langfuse — заглушка, не интеграция |
| 8 | SQLAlchemy pool default | "20 connections" | 5 connections | Неверный факт |
| 9 | orchestrator характеристика | "legacy helper" | 128 строк мёртвого кода | Не отмечен как dead code |
| 10 | auth_service приоритет | "OK для single-user" | Race condition при side-by-side | Недооценён risk |

---

*Этот анализ основан на чтении каждого файла проекта с верификацией каждого утверждения по коду. Размеры файлов, количество функций и зависимости подтверждены точным подсчётом.*
