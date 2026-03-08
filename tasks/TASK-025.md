---
id: TASK-025
title: "Bugfix: Runtime process management (kill-all, retry, stderr, timeout, budget model)"
type: bugfix
status: backlog
assigned_to: developer
priority: 25
feature: "runtime"
depends_on: []
---

# TASK-025: Runtime — исправление процесс-менеджмента

## Контекст

Архитектурный анализ (ARCHITECTURE_REVIEW.md) выявил 5 проблем в `runtime.py` — все связаны с управлением CLI-процессами. Эти баги каскадируют: kill-all (6.1) вызывает ложные circuit breaker failures (6.24), @retry не работает (6.19), stderr task утекает (6.20), process.wait может зависнуть навсегда (6.21), стоимость opus занижена 5x (6.22).

## Баги

### BUG-1 [CRITICAL] — kill-all убивает ВСЕ процессы (6.1, 6.24, 6.32)

**Файл:** `api/app/services/runtime.py:84-86`

```python
# Текущий код — убивает процессы ВСЕХ сессий:
for r in self._processes.values():
    await self._kill_process(r)
```

При side-by-side chat (ChatPage поддерживает 2 панели) отправка сообщения в одну панель убивает CLI-процесс другой. Каскадирует через circuit_breaker: 5 kill-ов за 60 секунд → OPEN state → обе панели заблокированы на 30 секунд.

**Исправление:** Убивать только процесс текущей сессии:
```python
running = self._processes.get(session_id)
if running:
    await self._kill_process(running)
```

### BUG-2 [DESIGN] — @retry на _launch_process — мёртвая логика (6.19)

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

`_launch_process` бросает `OSError`/`FileNotFoundError`, не `TransientAgentError`. Retry никогда не сработает.

**Исправление:** Изменить `retry_if_exception_type(TransientAgentError)` на `retry_if_exception_type(OSError)`.

### BUG-3 [RELIABILITY] — stderr_task leak при исключении (6.20)

**Файл:** `api/app/services/runtime.py:290-310`

```python
stderr_task = asyncio.create_task(process.stderr.read()) if process.stderr else None
async for line in process.stdout:  # если здесь exception...
    ...
await process.wait()
if stderr_task:
    stderr = await stderr_task  # ...сюда не дойдём → task leak
```

**Исправление:** Обернуть в try/finally:
```python
stderr_task = asyncio.create_task(process.stderr.read()) if process.stderr else None
try:
    async for line in process.stdout:
        ...
    await asyncio.wait_for(process.wait(), timeout=300)
    if stderr_task:
        stderr = await stderr_task
        ...
finally:
    if stderr_task and not stderr_task.done():
        stderr_task.cancel()
        try:
            await stderr_task
        except asyncio.CancelledError:
            pass
```

### BUG-4 [RELIABILITY] — process.wait() без timeout (6.21)

**Файл:** `api/app/services/runtime.py:307`

```python
await process.wait()  # может ждать вечно
```

**Исправление:** `await asyncio.wait_for(process.wait(), timeout=300)` (входит в try/finally из BUG-3).

### BUG-5 [ACCURACY] — budget не получает model name, cost opus занижена 5x (6.22)

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

При отсутствии `reported_cost` используется DEFAULT_PRICING ($3/$15 — sonnet). Для opus ($15/$75) стоимость занижена 5x.

**Исправление:** Добавить `model=event.get("model")` в вызов `record_usage()`. Значение `model` доступно в JSON event от CLI в поле `model`.

## Файлы для чтения

- `api/app/services/runtime.py` — основной файл изменений
- `api/app/services/budget.py` — сигнатура `record_usage()`, `compute_cost()`
- `api/app/services/circuit_breaker.py` — понимание каскадного эффекта
- `api/tests/test_runtime.py` — существующие тесты

## Acceptance Criteria

- [ ] `send_message()` убивает только процесс текущей сессии, не все
- [ ] `@retry` на `_launch_process` ловит `OSError` вместо `TransientAgentError`
- [ ] `stderr_task` корректно cancel'ится при исключении в `async for`
- [ ] `process.wait()` имеет timeout 300 секунд
- [ ] `record_usage()` получает параметр `model` из CLI event
- [ ] Существующие тесты в `test_runtime.py` проходят
- [ ] `pytest` без ошибок

## Ограничения

- Изменять только `api/app/services/runtime.py`
- Обновить тесты в `api/tests/test_runtime.py` если они затронуты изменениями
- Не менять API сервисов budget/circuit_breaker
