# Персональный роадмап: От текущего уровня к Production AI-Agent Architecture

**Дата:** 2026-03-07
**Основан на:** `research/ai-agent-systems.md` + `research/project_capability_analysis.md`
**Принцип:** Не общий AI-план — персонализированный маршрут на основе анализа реального проекта

---

## Содержание

1. [Оценка текущего уровня](#1-оценка-текущего-уровня)
2. [Определение целевого уровня](#2-определение-целевого-уровня)
3. [Gap-синтез: что мешает достичь цели](#3-gap-синтез-что-мешает-достичь-цели)
4. [Архитектура обучения: стадии](#4-архитектура-обучения-стадии)
5. [Проектный путь обучения](#5-проектный-путь-обучения)
6. [Теоретический путь обучения](#6-теоретический-путь-обучения)
7. [Граф обучения: зависимости навыков](#7-граф-обучения-зависимости-навыков)
8. [Контрольные точки (Milestones)](#8-контрольные-точки-milestones)
9. [Рекомендованный путь прогрессии](#9-рекомендованный-путь-прогрессии)

---

## 1. Оценка текущего уровня

### 1.1 Интегральный уровень

**Текущий уровень: Senior Engineer, начинающий специализацию в AI-системах**

Это не начинающий и не новичок в области. Это инженер с сильным системным мышлением, который уже проектирует AI-агентные системы — но пока на концептуальном уровне, без production-опыта эксплуатации.

### 1.2 Что уже можно решать

Проект ai-dev-agents демонстрирует способность:

- **Проектировать роль-ориентированные multi-agent системы** с разделением ответственности, bounded context для каждого агента, изоляцией файловой системы
- **Создавать межагентные протоколы** — структурированные блоки (Handoff, QA Result, Migration Brief) как самодостаточные контракты коммуникации
- **Строить многоуровневую архитектуру промптов**: системный промпт (роль) → протокол (форматы) → контекст проекта → задача (scope)
- **Реализовывать Planner-Executor паттерн**: TASK-*.md как единицы работы, lifecycle pending → in-progress → done → qa-pass/fail
- **Принимать обоснованные архитектурные решения** с документированием (ADR-pattern, GAPS.md, trade-off-анализ)
- **Применять Docker-изоляцию** для агентов: rw/ro volumes, namespace isolation
- **Строить полноценный API** для управления агентами: REST + WebSocket стриминг, AsyncIterator, агент как subprocess

### 1.3 Какую архитектуру уже можно проектировать

Текущий потолок — **Human-in-the-Loop Multi-Agent система** с фиксированным pipeline:

```
Architect → Planner → Developer → Reviewer (оркестрация: человек)
```

Это работоспособная архитектура с правильными принципами. Но она:
- Не автоматизирована (человек как orchestrator)
- Не наблюдаема (нет трейсинга LLM-вызовов)
- Не устойчива к сбоям (нет retry, checkpointing)
- Не масштабируема (один хост, нет горизонтального масштабирования)

### 1.4 Покрытие уровней (из анализа проекта)

```
Уровень 1 (Основы системного дизайна)      [██████████] ~85%
Уровень 2 (LLM-инженерия)                  [██████░░░░] ~55%
Уровень 3 (Архитектура AI-агентов)         [███████░░░] ~65%
Уровень 4 (Распределённые системы для AI)  [███░░░░░░░] ~25%
Уровень 5 (Production AI-архитектура)      [█░░░░░░░░░] ~5%
```

---

## 2. Определение целевого уровня

### 2.1 Целевая способность

**"Способность архитектировать и строить production-grade AI-агентные системы"**

### 2.2 Что это означает конкретно

Инженер на целевом уровне умеет:

**Проектирование системы:**
- Выбрать правильную архитектуру оркестрации (centralized/graph/event-driven/swarm) для конкретной задачи с обоснованием
- Спроектировать state machine для сложного multi-agent workflow с checkpointing и time-travel debugging
- Определить, когда нужен агентный цикл, а когда достаточно одного структурированного промпта
- Спроектировать систему памяти: какой тип (working/episodic/semantic/procedural), какое хранилище, какая стратегия retrieval

**Реализация:**
- Построить автоматический orchestrator с dynamic routing, parallel execution, error recovery
- Интегрировать observability (OTel трейсинг, token usage, cost per run) с первого дня
- Реализовать resilience: retry с exponential backoff, circuit breaker, idempotency keys, state checkpointing
- Построить RAG систему: hybrid retrieval (BM25 + dense embeddings) + reranking + RAG-as-Tool паттерн
- Внедрить guardrails против prompt injection, sandboxing для code execution

**Эксплуатация:**
- Понимать deградацию системы по метрикам до того, как она ломается
- Отлаживать сложный multi-agent workflow через distributed traces
- Оценивать качество агентов: trajectory-based evaluation, LLM-as-judge, regression benchmarks
- Управлять стоимостью: token budgets, semantic caching, model routing

**Архитектурные решения:**
- Принимать решения о trade-off между LangGraph / CrewAI / custom orchestrator для конкретного контекста
- Проектировать LLM-agnostic архитектуры с provider abstraction
- Интегрировать MCP-серверы и A2A протокол для inter-agent коммуникации

### 2.3 Benchmark цели

Инженер на целевом уровне способен построить систему, которая:
- Выдерживает 100+ параллельных agent runs без деградации
- Имеет P95 latency под контролем с алертингом
- Имеет cost per run известную и предсказуемую
- Восстанавливается автоматически после сбоев LLM API
- Детектирует деградацию качества агентов через eval метрики

---

## 3. Gap-синтез: что мешает достичь цели

На основе gap-анализа проекта, сгруппированные по приоритету:

### Приоритет 1 — Разблокируют архитектурный скачок (критические)

**Gap A: Автоматическая оркестрация**

Граф agent_links уже реализован в базе данных. Протоколы (Handoff Block) формализованы. Не хватает orchestrator-сервиса, читающего `next:` поле и автоматически запускающего следующего агента. Этот gap блокирует переход от "инструмент для разработчика" к "автономной системе".

*Что разблокирует:* параллельное выполнение задач, автоматический re-routing при ошибках, multi-pipeline execution.

**Gap B: Наблюдаемость (Observability)**

Без трейсинга LLM-вызовов, token usage и cost per task невозможно системно улучшать систему. Это не опциональный компонент — это инфраструктура обратной связи. Без неё все остальные улучшения делаются вслепую.

*Что разблокирует:* понимание поведения системы, оптимизацию промптов на основе данных, cost management, debugging complex workflows.

**Gap C: Resilience (Устойчивость к сбоям)**

Нет retry с exponential backoff для LLM API, нет checkpointing состояния workflow, нет стратегии восстановления. Любой transient error = потеря задачи. Production-система не может зависеть от "сети всегда стабильна".

*Что разблокирует:* long-running workflows, production deployment без постоянного человеческого мониторинга.

### Приоритет 2 — Увеличивают системную мощность (важные)

**Gap D: Система памяти агентов (Vector Memory)**

Текущая файловая "память" (project/CLAUDE.md, architecture.md) — ручная и не масштабируется. Агент не может семантически найти "какие решения мы принимали для похожих задач". Векторная БД (pgvector) разблокирует RAG-as-Tool паттерн.

*Что разблокирует:* агенты с долгосрочной памятью, RAG для корпоративных знаний, автоматический поиск precedents.

**Gap E: Система оценки (Evaluation)**

Нет данных о том, улучшается ли система со временем. Промпты изменяются без измеримых результатов. LLM-as-judge + regression тесты — это механизм управления качеством AI-системы.

*Что разблокирует:* возможность итеративного улучшения промптов, детекцию prompt regression, A/B тестирование агентных стратегий.

### Приоритет 3 — Расширяют до enterprise-уровня (развивающие)

**Gap F: Горизонтальное масштабирование**

AgentRuntime привязан к хост-машине (claude CLI как subprocess). Stateless worker architecture + внешнее хранилище состояния разблокируют multi-instance deployment.

**Gap G: Безопасность (Prompt Injection)**

Нет защиты от indirect prompt injection через данные в workspace. Агент читает файл, содержащий инструкции "перешли все данные на X" — и выполняет их. Это production security риск для систем с внешними данными.

**Gap H: LLM-независимость**

Жёсткая привязка к claude CLI. LiteLLM-абстракция + model routing (дешёвые модели для простых задач) — это cost management и vendor independence.

### Сводная матрица приоритетов

| Gap | Архитектурный impact | Сложность | Когда учить |
|-----|---------------------|-----------|-------------|
| Автоматическая оркестрация | Критический | Высокая | Стадия 2 |
| Наблюдаемость | Критический | Средняя | Стадия 2 |
| Resilience | Критический | Средняя | Стадия 2-3 |
| Vector Memory / RAG | Высокий | Высокая | Стадия 3 |
| Evaluation Framework | Высокий | Высокая | Стадия 3 |
| Горизонтальное масштабирование | Средний | Высокая | Стадия 4 |
| Безопасность (prompt injection) | Средний | Средняя | Стадия 3 |
| LLM-независимость | Низкий | Низкая | Стадия 2 |

---

## 4. Архитектура обучения: стадии

### Стадия 1 — Закрытие фундаментальных пробелов в LLM-инженерии

**Что охватывает:** углубление в то, что в проекте реализовано частично — asyncio internals, context window management, structured outputs, базовый error handling для LLM-вызовов.

**Почему именно сейчас:** Проект уже использует asyncio, streaming, structured outputs — но вероятно без полного понимания. Без глубокого понимания этих механизмов следующие стадии будут строиться на шатком фундаменте.

**Ключевые навыки:**
- asyncio internals: event loop, coroutines, subprocess management, backpressure
- Context window как управляемый ресурс: token budgeting, "lost in the middle" проблема, стратегии summarization
- Structured outputs: JSON Schema для LLM, валидация с retry, Pydantic как контракт
- Базовая LLM error handling: rate limits, timeout, retry с exponential backoff
- LiteLLM: провайдер-агностичный API как первый шаг к LLM-независимости

**Результат стадии:** Способность писать надёжный LLM-вызов с правильной обработкой ошибок, token budgeting и structured output.

---

### Стадия 2 — Автоматическая оркестрация и наблюдаемость

**Что охватывает:** переход от ручной оркестрации к автоматической. Observability как инфраструктура. LangGraph как основной инструмент graph orchestration.

**Почему именно сейчас:** Это самый высокий приоритет из gap-анализа. Автоматическая оркестрация + observability — это два навыка, которые вместе переводят систему из "прототипа" в "управляемую систему".

**Ключевые навыки:**
- LangGraph: StateGraph, TypedDict state, conditional edges, interrupt() для HITL
- Checkpointing: PostgresSaver / RedisSaver, time-travel debugging
- OpenTelemetry для AI: gen_ai semantic conventions, nested spans, correlation IDs
- LangSmith / Langfuse: интеграция трейсинга, анализ traces, cost tracking
- Event-driven orchestration: паттерн реакции на события (Handoff Block → trigger)
- Idempotency keys для действий с side effects

**Результат стадии:** Способность построить автоматический pipeline с трейсингом каждого LLM-вызова, checkpointing состояния и time-travel debugging при ошибках.

---

### Стадия 3 — Memory, RAG и Evaluation

**Что охватывает:** три связанных системы, которые превращают агента из "stateless executor" в "learning system".

**Почему именно сейчас:** После того как оркестрация автоматизирована и наблюдаема, следующий вопрос: "как агент улучшается со временем?" Это требует памяти (что было) и оценки (насколько хорошо).

**Ключевые навыки:**
- Vector embeddings: как работают, метрики сходства, выбор модели embeddings
- pgvector: HNSW индексы, hybrid search (BM25 + dense), операторы сходства
- RAG архитектура: naive → advanced → agentic. Hybrid retrieval + cross-encoder reranking
- RAG-as-Tool паттерн: retrieval по запросу агента, не встроенный в pipeline
- Memory types: episodic (история задач), semantic (знания о проекте), procedural (паттерны)
- LLM-as-Judge: методология, риски bias, структурированные rubrics
- Trajectory-based evaluation: оценка пути, а не только результата
- Eval harness: набор regression-тестов для агентного поведения
- Prompt injection protection: indirect injection через данные, mitigation strategies
- Action sandboxing: E2B, Docker network isolation для code execution агентов

**Результат стадии:** Способность построить агента с долгосрочной памятью, оценить его качество количественно и защитить от prompt injection.

---

### Стадия 4 — Production-архитектура

**Что охватывает:** всё необходимое для deployment, эксплуатации и масштабирования AI-агентной системы в production.

**Почему именно сейчас:** Это венец предыдущих стадий. Production-readiness требует всех нижележащих навыков.

**Ключевые навыки:**
- Stateless worker architecture: вынос состояния в Redis/БД, горизонтальное масштабирование
- Task queues для агентных систем: Redis Streams / SQS для буферизации и retry
- Circuit breaker паттерн: защита от cascading failures при деградации LLM API
- Multi-tenancy: изоляция данных и ресурсов между клиентами
- Model routing: дешёвые модели для простых задач, routing на основе complexity
- Semantic caching: кеширование LLM ответов (GPTCache, prompt caching)
- Cost budgets: token budgets per agent, cost per run enforcement
- Canary deployments для промптов: постепенный rollout новых промптов с eval
- Alerting: loop detection, cost overrun, error rate, latency P95

**Результат стадии:** Способность развернуть AI-агентную систему в production, которая масштабируется горизонтально, восстанавливается от сбоев и управляется по метрикам.

---

### Стадия 5 — Большие AI-системы и стандарты

**Что охватывает:** архитектура систем уровня enterprise, межсистемная интеграция агентов, стандарты протоколов.

**Ключевые навыки:**
- MCP (Model Context Protocol): разработка MCP-серверов, интеграция существующих инструментов
- A2A (Agent2Agent): federation агентов разных систем, Agent Cards, task lifecycle
- Temporal.io: durable workflow execution для долгоживущих агентных workflows
- Fine-tuning workflow: когда и как дообучать модели на агентных данных
- Large-scale evaluation: SWE-bench, GAIA, WebArena как benchmarks
- Compliance / Audit logging: полная история для регуляторных требований

**Результат стадии:** Способность проектировать AI-агентные системы уровня enterprise с inter-agent federation и compliance-ready audit trail.

---

## 5. Проектный путь обучения

Проекты построены на существующей кодовой базе ai-dev-agents — это ускоряет обучение, потому что контекст уже знаком.

### Проект P1: AgentRuntime — глубокое погружение

**Что строить:** Рефакторинг `services/runtime.py` с полным пониманием каждой строки. Добавить: retry с exponential backoff для LLM-вызовов, правильный backpressure для stdin/stdout pipes, graceful shutdown с cleanup.

**AI-агентная архитектура:** Single agent runtime с надёжным process management.

**Что развивает:**
- asyncio internals: event loop, subprocess, pipes, задержки
- LLM error handling: классификация ошибок (transient vs permanent), retry policy
- Graceful degradation: что делать при timeout, при OOM

**Новые концепции:** exponential backoff, backpressure, graceful shutdown patterns

**Связь с проектом:** Прямое улучшение существующего AgentRuntime — результат немедленно применим.

---

### Проект P2: Observability Layer

**Что строить:** Интегрировать OpenTelemetry в AgentRuntime. Каждый `send_message` и `run_task` — span. Вложенные spans для tool calls. Экспорт в Langfuse (self-hosted). Dashboard: token usage, cost per agent, latency per task.

**AI-агентная архитектура:** Distributed tracing для multi-agent pipeline.

**Что развивает:**
- OTel instrumentation: spans, attributes, context propagation
- gen_ai semantic conventions: стандартные атрибуты для LLM spans
- Cost tracking: token usage → $ cost per agent per task
- Langfuse: setup, traces view, промпт versioning

**Новые концепции:** correlation IDs, nested spans, "lost in traces" debugging, gen_ai conventions

**Связь с проектом:** Каждый запуск агента становится видимым в dashboard. Первый раз видно, сколько токенов тратит каждый агент.

---

### Проект P3: Автоматический Orchestrator

**Что строить:** Сервис, который читает `next:` поле из Handoff Block → автоматически запускает следующего агента. Использовать граф agent_links из БД как routing table. Начать с простого: Developer done → автоматически запускает Reviewer.

**AI-агентная архитектура:** Centralized orchestrator с event-triggered agent activation.

**Что развивает:**
- Event-driven triggers: как детектировать "задача завершена" без polling
- Dynamic routing: чтение routing logic из БД (agent_links)
- Error handling в pipeline: что делать если следующий агент недоступен
- Idempotency: как предотвратить двойной запуск агента

**Новые концепции:** orchestration state machine, event detection, routing tables, idempotency keys

**Связь с проектом:** Первый шаг к автономной системе — человек больше не копирует Handoff Block вручную.

---

### Проект P4: LangGraph Redesign

**Что строить:** Переписать pipeline Planner → Developer → Reviewer как LangGraph граф. State: текущая задача, статус, артефакты, ошибки. Добавить: checkpointing (PostgresSaver), interrupt() для human approval перед мержем, time-travel debugging.

**AI-агентная архитектура:** Graph orchestration с State machine, checkpointing и HITL gates.

**Что развивает:**
- LangGraph: StateGraph, TypedDict state, conditional edges
- Checkpointing: PostgresSaver, resume после сбоя
- HITL gates: interrupt() — пауза для human approval
- Time-travel debugging: откат к предыдущему checkpoint и replay

**Новые концепции:** State as first-class citizen, event sourcing vs snapshots, time-travel debugging

**Связь с проектом:** Существующий pipeline получает детерминизм, checkpointing и возможность resume после любого сбоя.

---

### Проект P5: Vector Memory для агентов

**Что строить:** pgvector в существующей PostgreSQL. Две коллекции: (1) episodic memory — история задач с embeddings описания + решения; (2) semantic memory — архитектурные решения (ADR) с embeddings. RAG-as-Tool: новый инструмент `search_past_decisions(query)` для агентов.

**AI-агентная архитектура:** Memory-augmented agents с hybrid retrieval.

**Что развивает:**
- Vector embeddings: как работают, выбор модели (text-embedding-3-small vs claude embeddings)
- pgvector: HNSW index, cosine similarity, hybrid search (BM25 + dense)
- RAG-as-Tool паттерн: агент сам решает, когда делать retrieval
- Memory consolidation: как episodic события превращаются в semantic знания

**Новые концепции:** HNSW index, hybrid retrieval, cross-encoder reranking, false memory риски

**Связь с проектом:** Architect-агент может найти "какие решения мы принимали для похожих архитектурных вопросов" без ручного контекста.

---

### Проект P6: Evaluation Framework

**Что строить:** Eval harness для Developer-агента. Набор из 20 regression задач с известными правильными решениями. LLM-as-Judge (Claude Sonnet) оценивает: (1) правильность кода; (2) соответствие архитектурным принципам; (3) наличие тестов. Dashboard: pass rate по версиям промпта.

**AI-агентная архитектура:** Offline evaluation pipeline с LLM-as-judge.

**Что развивает:**
- LLM-as-Judge: prompt для judge, структурированные rubrics, bias mitigation
- Trajectory evaluation: оценка пути (читал ли нужные файлы?) vs outcome (код работает?)
- Regression testing для промптов: что сломалось при изменении системного промпта
- Dataset curation: как собирать "golden" примеры из production трафика

**Новые концепции:** trajectory vs outcome evaluation, positional bias в LLM judge, golden datasets

**Связь с проектом:** Любое изменение промпта Developer-агента можно количественно сравнить с предыдущей версией.

---

### Проект P7: MCP-сервер для workspace

**Что строить:** MCP-сервер, экспортирующий workspace инструменты: `list_tasks`, `get_task`, `update_task_status`, `read_architecture_decisions`, `search_memory`. Подключить к Claude Code для агентов. Это заменяет кастомные shell-скрипты стандартным протоколом.

**AI-агентная архитектура:** MCP как стандартный tool integration layer.

**Что развивает:**
- MCP protocol: JSON-RPC 2.0, tools/resources/prompts, transport (stdio vs HTTP)
- Tool design: описание инструментов так, чтобы LLM корректно их вызывал
- MCP security: capabilities, authentication для workspace доступа

**Новые концепции:** MCP server/client модель, hub-and-spoke tool integration, agent card

**Связь с проектом:** Любой MCP-совместимый клиент может использовать workspace инструменты без adapter кода.

---

### Проект P8: Production Hardening

**Что строить:** Circuit breaker для LLM API вызовов (tenacity + custom circuit breaker). Semantic caching (Anthropic prompt caching для длинных системных промптов). Token budget enforcement per agent. Cost alerting: если задача превышает бюджет — HITL gate. Stateless AgentRuntime с хранением процессов в Redis.

**AI-агентная архитектура:** Production-grade agent runtime с resilience и cost control.

**Что развивает:**
- Circuit breaker паттерн: open/half-open/closed, failure threshold
- Semantic caching: Anthropic cache_control, когда caching выгоден
- Token budget management: tiktoken для подсчёта, enforcement механизм
- Stateless architecture: перенос _processes dict в Redis для multi-instance

**Новые концепции:** cascading failures, circuit breaker states, semantic caching economics, stateless workers

**Связь с проектом:** AgentRuntime становится production-grade: переживает перезапуски, не допускает cost overrun, восстанавливается от LLM API деградации.

---

## 6. Теоретический путь обучения

Некоторые концепции лучше понять теоретически перед практикой, иначе практика будет слепой.

### 6.1 Навыки, требующие теории ПЕРЕД практикой

**Концепция: "Lost in the middle" проблема**

Почему: Без понимания деградации LLM при заполнении контекста можно писать промпты, которые работают в тестах (короткий контекст) и ломаются в production (длинный контекст). Теория позволяет проектировать промпты правильно с первого раза.

Что изучить: оригинальная работа "Lost in the Middle" (Liu et al., 2023), позиционирование информации в контексте, деградация при 60-70% заполнения.

**Концепция: Причины Agent Loops (точная)**

Почему: Без понимания того, почему петли возникают (модель не различает "я пробовал это" и "это выполнено"), любые защиты будут неполными. Теория даёт правильную модель проблемы.

Что изучить: ReAct паттерн (Yao et al., 2022), механизм attention over history, "явная маркировка неудач" как решение.

**Концепция: Memory types и их failure modes**

Почему: Неправильный тип памяти создаёт false memory риск (агент "вспоминает" данные другого пользователя). Нужно понять типы до проектирования.

Что изучить: Working / Episodic / Semantic / Procedural memory классификация, failure modes каждого типа (temporal decay, false memory via similarity).

**Концепция: Trajectory vs Outcome evaluation**

Почему: Без этого различия можно создать eval, который пропускает агента с правильным ответом через неправильный путь (случайная удача). Это заблуждение дорого обходится в production.

Что изучить: SWE-bench методология, GAIA benchmark design, разница trajectory и outcome оценки.

**Концепция: Indirect Prompt Injection**

Почему: Это неочевидная угроза — большинство разработчиков защищаются от прямой инъекции, но не от непрямой (через данные в RAG, файлы, ответы API). Архитектурные решения нужно принять при проектировании, а не добавлять retrofit.

Что изучить: механизм indirect injection (агент "доверяет" извлечённому контенту), separation of data and instruction channels.

### 6.2 Навыки, где теория и практика идут вместе

**LangGraph** — теория (StateGraph, checkpointing) + немедленная практика (Проект P4). Изучать документацию параллельно с реализацией.

**OpenTelemetry** — понять gen_ai semantic conventions теоретически, потом инструментировать (Проект P2).

**RAG архитектура** — понять эволюцию naive → advanced → agentic RAG, потом строить (Проект P5).

**Circuit breaker паттерн** — понять state machine (open/half-open/closed) до реализации (Проект P8).

### 6.3 Навыки, где практика важнее теории

**asyncio internals** — документация и исходники полезны, но понимание приходит только через написание кода с subprocess, pipes, backpressure.

**Prompt engineering** — A/B тестирование формулировок можно изучить теоретически, но интуиция строится только через сотни итераций.

**Vector embeddings** — математика понятна теоретически, но "чувство" для хорошего vs плохого retrieval приходит через практику.

**LLM-as-Judge** — bias митигации понятны теоретически, но откалибровать судью под конкретную задачу — только через практику.

---

## 7. Граф обучения: зависимости навыков

### 7.1 Зависимости (что разблокирует что)

```
asyncio internals
    └── AgentRuntime refactor (P1)
        └── Observability Layer (P2)
            └── Cost tracking → Cost budgets (P8)
            └── Traces → Debugging complex workflows

LLM error handling (retry, backoff)
    └── AgentRuntime refactor (P1)
        └── Circuit breaker (P8)
            └── Resilient production runtime

LangGraph (State, checkpointing)
    └── Automatic Orchestrator design (P3→P4)
        └── HITL gates
        └── Time-travel debugging

OpenTelemetry + LangSmith/Langfuse
    └── Traces per LLM call
        └── Cost per agent
        └── Prompt performance data
            └── Evaluation Framework (P6) — нужны данные для eval

Vector embeddings + pgvector
    └── Vector Memory (P5)
        └── RAG-as-Tool
            └── Memory-augmented agents

LLM-as-Judge
    └── Evaluation Framework (P6)
        └── Prompt regression testing
        └── Canary deployments для промптов

MCP Protocol
    └── MCP Server (P7)
        └── Standard tool integration
        └── A2A Federation (Стадия 5)

Stateless architecture
    └── Horizontal scaling
        └── Multi-instance deployment
```

### 7.2 Критический путь — самый быстрый маршрут к production-уровню

Минимальный набор навыков, дающих максимальный сдвиг:

```
asyncio internals
    ↓
LLM error handling
    ↓
OTel observability (самый важный gap)
    ↓
LangGraph + checkpointing
    ↓
Automatic orchestration
    ↓
[FIRST REAL PRODUCTION MILESTONE]
    ↓
Vector memory + RAG
    ↓
Evaluation framework
    ↓
[SECOND MILESTONE: улучшаемая система]
    ↓
Production hardening (circuit breaker, scaling)
    ↓
[TARGET LEVEL]
```

### 7.3 Параллельные треки (можно учить одновременно)

**Трек A (Infrastructure):** asyncio → OTel → Circuit breaker → Stateless scaling

**Трек B (AI-Architecture):** LangGraph → Automatic orchestration → Memory systems → Evaluation

**Трек C (Standards):** LiteLLM → MCP → A2A

Треки A и B можно вести параллельно после Стадии 1. Трек C — независим, можно добавить в любое время.

### 7.4 Концепции-разблокировщики

Это навыки, изучение которых открывает доступ к наибольшему числу других навыков:

1. **OTel distributed tracing** — разблокирует: debugging, cost tracking, eval data collection, prompt performance analysis
2. **LangGraph StateGraph** — разблокирует: automatic orchestration, checkpointing, HITL, time-travel debugging, parallel execution
3. **Vector embeddings** — разблокирует: RAG, memory systems, semantic search, semantic caching

---

## 8. Контрольные точки (Milestones)

### Milestone 1: Надёжный LLM-инженер

**Что должно быть реализовано:** AgentRuntime (P1) с полным пониманием кода, базовая observability (P2), LiteLLM абстракция.

**Что должно быть понято:**
- Почему asyncio event loop не блокируется при subprocess.communicate()
- Как работает backpressure в asyncio pipes
- Разница между transient и permanent LLM errors
- "Lost in the middle" проблема и как её учитывать при проектировании промптов

**Что можно строить:** Надёжные LLM-приложения с правильной обработкой ошибок, стриминга и token management. AgentRuntime перестаёт быть "чёрным ящиком".

**Метрика:** Трейс каждого LLM-вызова виден в Langfuse с token usage и стоимостью.

---

### Milestone 2: Автоматический Multi-agent Orchestrator

**Что должно быть реализовано:** P3 (автоматический handoff) + P4 (LangGraph pipeline) с checkpointing.

**Что должно быть понято:**
- Как LangGraph StateGraph отличается от простого pipeline
- Почему checkpointing после каждого узла — не переусложнение, а обязательное условие
- Как проектировать idempotent actions
- Difference между event-driven и polling для trigger detection

**Что можно строить:** Multi-agent системы, которые работают без human-in-the-loop, восстанавливаются от сбоев, поддерживают time-travel debugging.

**Метрика:** Developer → Reviewer handoff происходит автоматически без участия человека. При сбое LLM API система resume с последнего checkpoint.

---

### Milestone 3: Observability-driven AI System

**Что должно быть реализовано:** P2 полностью + данные из production трафика в Langfuse + cost per task dashboard.

**Что должно быть понято:**
- Какие span attributes критичны для debugging complex failures
- Как читать nested traces и находить root cause
- Как correlation IDs позволяют связать все действия одного run
- Что "cost per task" говорит об эффективности агента

**Что можно строить:** Системы, где каждая ошибка расследуется через traces, а не через логи. Стоимость каждого агентного run известна.

**Метрика:** Любую ошибку агента можно диагностировать по traces за < 5 минут.

---

### Milestone 4: Memory-augmented, Evaluated Agent

**Что должно быть реализовано:** P5 (vector memory) + P6 (eval framework).

**Что должно быть понято:**
- Как выбрать тип памяти для конкретного use case
- Почему hybrid retrieval (BM25 + dense) лучше pure semantic search для большинства задач
- Что LLM-as-judge с правильными rubrics и без — это разница между сигналом и шумом
- Как trajectory evaluation отличается от outcome и когда каждый нужен

**Что можно строить:** Агентов, которые используют знания из прошлых задач. Системы, где изменение промпта можно количественно сравнить с предыдущей версией.

**Метрика:** Developer-агент находит релевантные ADR из прошлого при проектировании нового компонента. Eval pass rate > 80% на regression dataset.

---

### Milestone 5: Production-grade AI System

**Что должно быть реализовано:** P7 (MCP) + P8 (production hardening).

**Что должно быть понято:**
- Как circuit breaker защищает от cascading failures
- Когда semantic caching экономически выгоден (высокий reuse rate запросов)
- Как stateless workers с Redis state management позволяют горизонтальное масштабирование
- Trade-off между consistency и availability для agent state при network partition

**Что можно строить:** AI-агентные системы, готовые к production deployment: горизонтально масштабируемые, с cost budgets, с MCP-стандартизированными инструментами.

**Метрика:** AgentRuntime работает в 3 экземплярах параллельно без конфликтов. Cost per task enforcement предотвращает runaway расходы.

---

### Milestone 6: Large-scale AI Architect

**Что должно быть реализовано:** A2A integration, Temporal.io для long-running workflows, canary deployments для промптов.

**Что должно быть понято:**
- Как A2A позволяет federate агентов разных систем
- Когда Temporal.io оправдан вместо LangGraph (долгоживущие workflows с днями/неделями жизни)
- Как canary deployment для промптов работает как feature flags для AI-поведения
- Compliance requirements: что нужно логировать для audit trail

**Что можно строить:** AI-агентные системы enterprise-уровня с federation, audit trail, long-running дуруемыми workflows.

---

## 9. Рекомендованный путь прогрессии

### 9.1 Принципы приоритизации

1. **Строй на том, что уже есть.** Каждый проект улучшает существующий ai-dev-agents, а не создаёт новый с нуля. Это ускоряет обучение — контекст уже знаком.

2. **Observability — первый приоритет.** Без видимости системы все последующие улучшения делаются вслепую. Начни с OTel + Langfuse.

3. **Автоматизируй только то, что понял вручную.** Текущая ручная оркестрация — правильная точка старта (D-002). Теперь, когда цикл отлажен, автоматизация оправдана.

4. **Критический путь важнее полного покрытия.** Быстрый путь через P1→P2→P3→P4 даёт больше, чем медленное изучение всего.

### 9.2 Рекомендованная последовательность

#### Фаза 1: Фундамент (Стадия 1)

```
Теория: asyncio internals (event loop, subprocess, pipes)
    → P1: AgentRuntime refactor (retry, backpressure, graceful shutdown)

Теория: OTel gen_ai conventions + Langfuse setup
    → P2: Observability layer (spans, cost tracking, dashboard)

Теория: LiteLLM провайдер-агностичный API
    → Замена claude CLI на LiteLLM wrapper в AgentRuntime
```

**Итог фазы 1:** AgentRuntime становится понятным, надёжным и observable. Это немедленно повышает уверенность в работе со всей системой.

---

#### Фаза 2: Автоматическая оркестрация (Стадия 2)

```
Теория: LangGraph (StateGraph, TypedDict, conditional edges)
    → P3: Простой автоматический orchestrator (Handoff Block → trigger)

Теория: Checkpointing (event sourcing vs snapshots, idempotency)
    → P4: LangGraph pipeline с PostgresSaver + interrupt() для HITL
```

**Итог фазы 2:** Достигнут Milestone 2. Первый раз система работает автономно без copy/paste между агентами.

---

#### Фаза 3: Интеллект и качество (Стадия 3)

```
Теория: Vector embeddings + hybrid retrieval + RAG архитектура
    → P5: pgvector memory (episodic + semantic) + RAG-as-Tool

Теория: LLM-as-Judge методология + trajectory evaluation
    → P6: Eval harness для Developer-агента + regression dataset

Теория: Indirect prompt injection + mitigation strategies
    → Аудит существующих агентов + добавление защитных механизмов
```

**Итог фазы 3:** Достигнут Milestone 4. Агент с памятью, оцениваемый количественно.

---

#### Фаза 4: Production и стандарты (Стадии 4-5)

```
P7: MCP-сервер для workspace инструментов

Теория: Circuit breaker, stateless scaling, cost management
    → P8: Production hardening (circuit breaker, semantic caching, stateless runtime)

Теория: A2A protocol, Temporal.io
    → Интеграция с внешними агентами, long-running workflows
```

**Итог фазы 4:** Достигнут Milestone 5-6. Production-grade система.

---

### 9.3 Итоговая временная перспектива

Этапы не привязаны к конкретным срокам — каждый человек движется с разной скоростью. Важна последовательность:

```
[Сейчас]
  Senior Engineer + AI Systems (концептуальный уровень)

    ↓ Фаза 1
  Надёжный LLM-инженер
  (asyncio понят, система observable, LLM calls reliable)

    ↓ Фаза 2
  Multi-agent Orchestrator
  (первая автономная система, LangGraph освоен)

    ↓ Фаза 3
  Memory-augmented + Evaluated Agent
  (система улучшается на основе данных)

    ↓ Фаза 4
  [ЦЕЛЬ] Production AI-Agent Architect
  (может архитектировать и строить production-grade AI-системы)
```

### 9.4 Сигналы правильного прогресса

Ты движешься в правильном направлении, если:

- После P2: Можешь назвать точную стоимость в $ любого запуска Developer-агента
- После P4: При сбое LLM API в середине задачи — система resume без потери прогресса
- После P5: Architect-агент сам находит релевантные прошлые ADR без подсказки человека
- После P6: Изменение промпта Developer-агента сопровождается количественным сравнением с предыдущей версией
- После P8: AgentRuntime запущен в 2 параллельных инстансах без конфликтов

Ты отклоняешься от пути, если:

- Строишь новый проект вместо улучшения существующего (контекст теряется)
- Пропускаешь observability и строишь "следующие фичи" (оптимизация вслепую)
- Автоматизируешь оркестрацию без checkpointing (хрупкая автоматизация хуже ручной)
- Изучаешь фреймворки ради фреймворков без привязки к конкретной проблеме

---

*Этот роадмап построен исключительно на основе анализа проекта ai-dev-agents и исследования ландшафта AI-агентных систем. Он отражает реальные gaps, реальные приоритеты и реальную архитектуру — не универсальный план.*
