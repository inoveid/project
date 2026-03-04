# Agent Console

Web-приложение для управления AI-агентами. Python FastAPI (backend) + React TypeScript (frontend) + PostgreSQL.

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
