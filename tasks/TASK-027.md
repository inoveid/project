---
id: TASK-027
title: "Bugfix: Backend reliability (pool, memory, judge, eval, security)"
type: bugfix
status: backlog
assigned_to: developer
priority: 27
feature: "backend-reliability"
depends_on: []
---

# TASK-027: Backend — reliability и correctness fixes

## Контекст

Архитектурный анализ выявил 6 независимых проблем в разных backend-модулях. Каждая — точечное исправление в 1 файле. Не зависят друг от друга и от TASK-025/026.

## Баги

### BUG-1 [RELIABILITY] — Нет pool_pre_ping (6.6)

**Файл:** `api/app/database.py`

```python
engine = create_async_engine(settings.database_url, echo=False)
```

Нет `pool_pre_ping=True` — stale connections не обнаруживаются после restart PostgreSQL.

**Исправление:**
```python
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
```

### BUG-2 [QUALITY] — memory_service: input_type="document" для query embeddings (6.40)

**Файл:** `api/app/services/memory_service.py:40-42`

```python
async def _embed(text_input: str) -> list[float]:
    client = voyageai.Client(api_key=settings.voyage_api_key)
    result = await asyncio.to_thread(
        client.embed, [text_input], model=EMBEDDING_MODEL, input_type="document"
    )
```

`_embed()` используется и для сохранения (document), и для поиска (query). Voyage AI оптимизирует embeddings по-разному для `input_type="document"` vs `"query"`. Для поиска используется неправильный тип → снижение quality retrieval.

**Исправление:** Добавить параметр `input_type`:
```python
async def _embed(text_input: str, input_type: str = "document") -> list[float]:
    client = voyageai.Client(api_key=settings.voyage_api_key)
    result = await asyncio.to_thread(
        client.embed, [text_input], model=EMBEDDING_MODEL, input_type=input_type
    )
```
И вызывать `_embed(query, input_type="query")` в `search_memories()`.

### BUG-3 [TYPING] — judge_service return type annotation не соответствует реальности (6.41)

**Файл:** `api/app/services/judge_service.py:153`

Сигнатура: `async def judge_agent_output(...) -> JudgeResponse:`
Фактический return: `return response, token_usage` — `tuple[JudgeResponse, dict]`.

**Исправление:** Изменить аннотацию на `-> tuple[JudgeResponse, dict]:`.

### BUG-4 [RELIABILITY] — Background eval task: status застревает на "running" при ошибке (6.43)

**Файл:** `api/app/routers/evaluations.py:75-80`

```python
async def _run_eval():
    from app.database import async_session
    async with async_session() as session:
        await eval_service.execute_eval_run(session, run.id, case_ids=case_ids)
```

Нет try/except. Если `execute_eval_run()` бросает исключение, run остаётся `status="running"` навсегда. Frontend бесконечно polling'ит (useEvalRun refetchInterval: 3000 при status "running").

**Исправление:**
```python
async def _run_eval():
    from app.database import async_session
    async with async_session() as session:
        try:
            await eval_service.execute_eval_run(session, run.id, case_ids=case_ids)
        except Exception:
            from app.models import EvalRun
            run_obj = await session.get(EvalRun, run.id)
            if run_obj and run_obj.status == "running":
                run_obj.status = "failed"
                await session.commit()
```

### BUG-5 [SECURITY] — path traversal startswith edge case (6.61)

**Файл:** `mcp-workspace/tools/specs.py:74-78`

```python
filepath = os.path.normpath(os.path.join(specs_path, filename))
if not filepath.startswith(specs_path):
    return "Error: path traversal not allowed."
```

`startswith()` — строковая операция. Edge case: `specs_path="/workspace/process/specs"`, input `"../specs_evil/secret.md"` → normpath → `"/workspace/process/specs_evil/secret.md"` → `startswith("/workspace/process/specs")` = **TRUE**.

**Исправление:**
```python
if not filepath.startswith(specs_path + os.sep) and filepath != specs_path:
```
Или (Python 3.9+): `Path(filepath).is_relative_to(Path(specs_path))`.

### BUG-6 [SECURITY] — safe.directory wildcard (6.65)

**Файл:** `api/entrypoint.sh:15`

```bash
git config --global --add safe.directory '*'
```

Отключает git ownership checks для ВСЕХ директорий. В Docker-контейнере обосновано, но wildcard излишне широк.

**Исправление:**
```bash
git config --global --add safe.directory /workspace
```

## Файлы для чтения

- `api/app/database.py` — engine creation
- `api/app/services/memory_service.py` — `_embed()`, `search_memories()`
- `api/app/services/judge_service.py` — `judge_agent_output()` return
- `api/app/routers/evaluations.py` — `_run_eval()` background task
- `api/app/services/eval_service.py` — `execute_eval_run()` для понимания exceptions
- `mcp-workspace/tools/specs.py` — `get_spec()` path validation
- `api/entrypoint.sh` — git config

## Acceptance Criteria

- [ ] `pool_pre_ping=True` в database.py
- [ ] `_embed()` принимает `input_type` параметр, `search_memories()` использует `input_type="query"`
- [ ] `judge_agent_output()` имеет корректную return type annotation `tuple[JudgeResponse, dict]`
- [ ] `_run_eval()` ловит исключения и ставит status="failed"
- [ ] `get_spec()` защищён от sibling-directory traversal
- [ ] `safe.directory` указывает конкретный путь `/workspace`
- [ ] `pytest` проходит без ошибок

## Ограничения

- Точечные изменения — каждый баг в 1 файле
- Не менять API/сигнатуры публичных функций (кроме judge return type annotation)
- `_embed()` — добавить параметр с default value, не ломая существующие вызовы
