# Agent Console

Web-приложение для управления AI-агентами. Python FastAPI (backend) + React TypeScript (frontend) + PostgreSQL.

## Документация

- [ARCHITECTURE.md](ARCHITECTURE.md) — архитектурная карта: модули, потоки данных, WS protocol, LangGraph workflow, dependency graph, how-to guides
- [DANGER_ZONES.md](DANGER_ZONES.md) — файлы с высоким blast radius: что проверять после изменений, какие тесты запускать

## Структура

```
app/
├── api/          ← Backend: FastAPI + SQLAlchemy + Alembic
│   ├── app/
│   │   ├── main.py        — точка входа, подключение роутеров
│   │   ├── config.py      — настройки (pydantic-settings, префикс AC_)
│   │   ├── database.py    — engine + session factory
│   │   ├── models/        — SQLAlchemy ORM модели
│   │   ├── schemas/       — Pydantic request/response схемы
│   │   ├── routers/       — HTTP endpoints + WebSocket
│   │   └── services/      — бизнес-логика
│   └── alembic/           — миграции БД
├── web/          ← Frontend: React + Vite + Tailwind + TanStack Query
│   └── src/
│       ├── api/           — fetch wrappers (типизированные)
│       ├── hooks/         — React hooks (queries, mutations, WebSocket)
│       ├── pages/         — маршруты (Dashboard, TeamPage, ChatPage)
│       ├── components/    — UI-компоненты
│       └── types/         — TypeScript типы
└── docker-compose.dev.yml
```

## Команды

| Действие | Команда |
|----------|---------|
| Запуск всего стека | `make dev` (из app/) |
| Только backend | `cd api && uvicorn app.main:app --reload` |
| Только frontend | `cd web && npm run dev` |
| Тесты backend | `cd api && pytest` |
| Тесты frontend | `cd web && npm test` |
| Линтинг frontend | `cd web && npm run lint` |
| Новая миграция | `cd api && alembic revision --autogenerate -m "описание"` |
| Применить миграции | `cd api && alembic upgrade head` |
| Сборка frontend | `cd web && npm run build` |

## Конвенции кода

### Backend

- **Файлы**: snake_case (`team_service.py`)
- **Модели**: PascalCase класс, таблица — plural snake_case (`class Team` → `teams`)
- **Роутеры**: один файл на ресурс, `router = APIRouter()`
- **Сервисы**: один файл на ресурс, async-функции принимают `AsyncSession` + Pydantic-схему
- **Схемы**: `{Resource}Create`, `{Resource}Update`, `{Resource}Read` — Pydantic v2
- **Импорты**: абсолютные от корня пакета (`from app.models import Team`)

### Frontend

- **Файлы**: PascalCase для компонентов (`TeamCard.tsx`), camelCase для утилит (`client.ts`)
- **Компоненты**: именованные экспорты (`export function TeamCard`)
- **Хуки**: `use{Resource}s` для списка, `use{Resource}` для одного, `useCreate{Resource}` для мутации
- **API**: каждый файл в `api/` экспортирует типизированные функции (`getTeams`, `createTeam`)
- **Маршруты**: `/` — Dashboard, `/teams/:id` — TeamPage, `/chat/:sessionId` — ChatPage

### API-конвенции (как добавить endpoint)

1. Создай Pydantic-схемы в `api/app/schemas/{resource}.py`
2. Создай SQLAlchemy модель в `api/app/models/{resource}.py`, зарегистрируй в `models/__init__.py`
3. Создай сервис в `api/app/services/{resource}_service.py`
4. Создай роутер в `api/app/routers/{resource}.py`, подключи в `main.py`
5. Создай миграцию: `alembic revision --autogenerate -m "add {resource}"`

### Тестовые конвенции

- Backend: `api/tests/test_{resource}.py`, fixtures в `conftest.py`
- Frontend: `*.test.tsx` рядом с компонентом или в `__tests__/`
- Мокать: `database.get_db` (backend), `fetch`/`api/*` (frontend)

## Что НЕ читать

- `node_modules/`, `dist/`, `.vite/`
- `__pycache__/`, `.pytest_cache/`
- `alembic/versions/` — читай только последнюю миграцию при необходимости
- `.env` (секреты)

## Архитектура (для AI-агентов)

### Как работает chat flow

```
Client ↔ WS (proxy, ws.py) ↔ Redis ↔ Worker (worker.py → LangGraph → SDK)
```

- `ws.py` — тонкий proxy (~91 строк), не содержит бизнес-логики
- `worker.py` — единственный процесс, выполняющий LangGraph граф
- `event_bus.py` — Redis pub/sub транспорт между ними
- `graph_service.py` — 6 LangGraph nodes (run_agent, gate, notify_handoff, auto_handoff, complete, blocked)

### EventSender Protocol

Graph nodes принимают `ws` через configurable, но это НЕ WebSocket:

```python
# graph_service.py
class EventSender(Protocol):
    async def send_json(self, data: dict[str, Any]) -> None: ...
```

В Worker это `EventPublisher` (→ Redis), в тестах — любой mock с `send_json`.

## Перед правкой — обязательно прочитай

| Что правишь | Что прочитать |
|-------------|---------------|
| worker.py | DANGER_ZONES.md §1, event_bus.py, graph_service.py |
| ws.py | DANGER_ZONES.md §3, event_bus.py |
| graph_service.py | DANGER_ZONES.md §2, handoff_server.py, worker.py |
| event_bus.py | DANGER_ZONES.md §1.5, ws.py, worker.py |
| runtime/ | DANGER_ZONES.md §2, worker.py |
| types/index.ts | chatEventHandler.ts (WsIncoming union должен совпадать) |
| chatEventHandler.ts | types/index.ts, graph_service.py (какие events отправляются) |
| task_service.py | worker.py (_try_update_task_status), routers/tasks.py |
| config.py | Все импортёры (13+), .env.example |

## Частые ошибки AI-агентов

1. **Buffer race condition** — в ws.py подписка на Redis events ДОЛЖНА быть ДО чтения buffer. Иначе события между buffer read и subscribe теряются
2. **Забыть cleanup children** — при остановке сессии нужно остановить все дочерние (handoff sub-sessions). См. handle_session() finally block
3. **Добавить WS event type только на backend** — нужно также добавить в `WsIncoming` (types/index.ts) и в `handleEvent` switch (chatEventHandler.ts), иначе событие молча игнорируется
4. **Менять VALID_TRANSITIONS без проверки worker** — worker.py вызывает _try_update_task_status, и невалидный переход логируется как ошибка
5. **expire_on_commit в database.py** — менять на True нельзя, сломает все graph nodes которые читают ORM после commit
6. **Два процесса, два checkpointer** — API (main.py) и Worker оба инициализируют AsyncPostgresSaver. Должны использовать одинаковый database_url
7. **EventPublisher ≠ WebSocket** — в worker.py graph nodes получают EventPublisher через configurable["websocket"], но это НЕ реальный WebSocket

## Тесты — что запускать

| После изменения в | Запусти |
|-------------------|---------|
| worker.py | `pytest tests/test_ws.py tests/test_runtime.py -v` |
| ws.py | `pytest tests/test_ws.py -v` |
| graph_service.py | `pytest tests/test_handoff.py -v` |
| runtime/ | `pytest tests/test_runtime.py -v` |
| event_bus.py | `pytest tests/test_ws.py tests/test_notification_service.py -v` |
| task_service.py | `pytest tests/test_tasks.py tests/test_task_service.py -v` |
| notification_service.py | `pytest tests/test_notification_service.py tests/test_notifications_ws.py -v` |
| hooks/chat/* | `cd web && npm test -- --run chatEventHandler useChat` |
| types/index.ts | `cd web && npm run build && npm test` |
| Любой router | `pytest tests/test_{resource}.py -v` |
| Любой frontend | `cd web && npm run build && npm run lint` |
