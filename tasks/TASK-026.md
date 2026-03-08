---
id: TASK-026
title: "Bugfix: Graph service — sub-agent session lifecycle"
type: bugfix
status: backlog
assigned_to: developer
priority: 26
feature: "graph-service"
depends_on: [TASK-025]
---

# TASK-026: Graph service — жизненный цикл sub-agent сессий

## Контекст

Архитектурный анализ выявил 2 проблемы с lifecycle sub-agent сессий: они не закрываются в БД после завершения (6.12) и их CLI-процессы остаются orphan при WebSocket disconnect (6.36). Зависит от TASK-025 (kill-all fix), т.к. после TASK-025 `runtime.stop_session()` больше не убивает все процессы.

## Баги

### BUG-1 [BUG] — Sub-agent sessions не закрываются в БД (6.12)

**Файл:** `api/app/services/graph_service.py:114-116`

```python
if is_sub:
    await runtime.stop_session(session_id)
```

`runtime.stop_session()` убивает CLI-процесс и удаляет из `_processes` dict, но **не вызывает** `session_service.stop_session(db, session_id)` для обновления статуса в БД. Sub-agent сессии остаются `status="active"` навсегда.

Последствия:
- `get_sessions()` фильтрует по `status == "active"` — orphaned sub-sessions загрязняют список
- Нет способа отличить реально активную сессию от orphaned sub-agent

**Исправление:** Добавить `await stop_session(db, session_id)` из `session_service` после `runtime.stop_session()`:
```python
if is_sub:
    await runtime.stop_session(session_id)
    await stop_session(db, session_id)
```

### BUG-2 [RESOURCE LEAK] — Sub-agent process orphan при WS disconnect (6.36)

**Файл:** `api/app/routers/ws.py` (disconnect handler)

Sub-agent cleanup (`runtime.stop_session(sub_session_id)`) вызывается **только** в `run_agent_node` при нормальном завершении. При WS disconnect:
1. `ws.py` убивает только main session process
2. Sub-agent CLI-процесс остаётся запущенным (orphan)
3. `_processes[sub_session_id]` не очищается

**Исправление:** При WS disconnect убивать все процессы, связанные с thread_id. Для этого:

1. В `graph_service.py` — трекать sub-session IDs в `WorkflowState` или отдельном mapping
2. В `ws.py` — при disconnect убивать main + все sub-agent процессы

Альтернативный подход (проще): в `ws.py` при disconnect вызывать `runtime.stop_all_sessions()` или итерировать `runtime._processes` для cleanup всех процессов, зарегистрированных в runtime.

## Файлы для чтения

- `api/app/services/graph_service.py` — `run_agent_node`, `gate_node`, `WorkflowState`
- `api/app/routers/ws.py` — WebSocket handler, disconnect cleanup
- `api/app/services/session_service.py` — `stop_session()` сигнатура
- `api/app/services/runtime.py` — `stop_session()`, `_processes` dict

## Acceptance Criteria

- [ ] Sub-agent сессия получает `status="completed"` (или `"stopped"`) в БД после завершения handoff
- [ ] При WS disconnect CLI-процессы sub-агентов корректно завершаются (нет orphan processes)
- [ ] `_processes` dict не содержит stale entries для sub-agent сессий
- [ ] `get_sessions()` не возвращает orphaned sub-agent сессии
- [ ] `pytest` проходит без ошибок
- [ ] Нормальный handoff flow (approve → sub-agent работает → done) не нарушен

## Ограничения

- Изменять: `api/app/services/graph_service.py`, `api/app/routers/ws.py`
- Не менять API `session_service` — использовать существующий `stop_session()`
- Не менять `WorkflowState` type если не необходимо для трекинга sub-sessions
