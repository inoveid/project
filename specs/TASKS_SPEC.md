# Спецификация: Tasks

## Контекст

Tasks — основная рабочая единица платформы. Задача привязана к продукту и команде,
проходит через агентов согласно workflow команды, завершается когда последний агент
подтверждает выполнение.

Итоговая архитектура:

```
Business → Product → Task ← Team
                      ↑
                   Session (task_id FK)
                      ↓
                   Agent (prompts[])
```

Смежные спеки:
- `CHANGES_SPEC.md` — Business, Product, System Agent (реализовано в TASK-041..044)
- Canvas / Team Workflow — отдельная спека (взаимосвязи агентов, workflow, промпты)

---

## 1. Модель данных

### 1.1 Task (новая таблица)

**Таблица: `tasks`**

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID PK | |
| title | str(500) | Название задачи |
| description | text, nullable | Описание |
| product_id | UUID FK → products, nullable | Продукт (даёт workdir) |
| team_id | UUID FK → teams, nullable | Команда-исполнитель |
| starting_agent_id | UUID FK → agents, nullable | Агент с которого начинается задача |
| status | str | Статус (см. ниже) |
| created_at | datetime | |

**Статусы:**
```
backlog → in_progress → awaiting_user → in_progress (цикл)
                    ↓
                   done
                   error
```

| Статус | Описание |
|--------|----------|
| `backlog` | Создана, ещё не запущена |
| `in_progress` | Агент работает |
| `awaiting_user` | Агент запросил handoff, ждёт approve/reject |
| `done` | Задача выполнена (последний агент завершил) |
| `error` | Произошла ошибка на каком-либо этапе |

**Переходы статусов:**

| Переход | Триггер |
|---------|---------|
| `backlog → in_progress` | Кнопка, drag, System Agent — после валидации |
| `in_progress → awaiting_user` | WS событие `approval_required` (автоматически) |
| `awaiting_user → in_progress` | WS событие approve (автоматически) |
| `in_progress → done` | Ручной drag или последний агент завершил |
| `in_progress → error` | WS событие `error` (автоматически) |
| `done → in_progress` | Ручной drag |
| `error → in_progress` | Ручной drag |

**Валидация перед переходом в `in_progress`:**
- title заполнен
- description заполнен
- product_id заполнен
- team_id заполнен
- starting_agent_id заполнен

---

### 1.2 Session (изменение)

Добавить поле:

| Поле | Тип | Описание |
|------|-----|----------|
| task_id | UUID FK → tasks, nullable | Задача (NULL для System Agent сессий) |

**Жизненный цикл сессии в контексте задачи:**
Сессия агента остаётся открытой (`status = in_progress`) пока задача находится
на этапе, где возможен возврат к этому агенту. Сессия закрывается только когда
задача перешла дальше по цепочке и возврат невозможен (определяется workflow
команды — отдельная Canvas-спека).

---

### 1.3 Agent (изменение)

Добавить поле:

| Поле | Тип | Описание |
|------|-----|----------|
| prompts | JSONB, default `[]` | Список промптов агента |

**Формат промпта:**
```json
[
  {"id": "uuid", "name": "Начать разработку", "content": "Реализуй задачу: {{task_description}}"},
  {"id": "uuid", "name": "Исправить замечания", "content": "Исправь: {{reviewer_notes}}"}
]
```

Промпты используются Canvas-ом для настройки handoff-цепочек.
На фронте в Tasks-задачах поле `prompts` хранится на беке, UI для управления
промптами реализуется в Canvas-спеке.

---

## 2. workdir Resolution

В `ws.py`, при старте сессии — логика выбора workdir:

```python
if session.task_id and session.task.product_id:
    workdir = session.task.product.workspace_path
else:
    workdir = None  # System Agent — управляет через API, не нужен workdir
```

`agent.config.workdir` становится неактуальным, не используется.

---

## 3. Автоматическое обновление task.status из WS-событий

В `ws.py`, при получении WS-событий от агента — обновлять `task.status`:

| WS событие | task.status |
|------------|-------------|
| `approval_required` | `awaiting_user` |
| approve (`Command(resume=True)`) | `in_progress` |
| `error` | `error` |

`done` и `in_progress` при старте — управляются вручную или через drag.

---

## 4. Запуск задачи

Три способа перевести задачу в `in_progress`:

1. **Кнопка в карточке/модале** — кнопка "Начать" на Task Card или в Task Modal
2. **Drag** — перетащить карточку из `backlog` в `in_progress` на Kanban
3. **System Agent** — команда в GlobalChatWidget (System Agent вызывает API)

Все три способа запускают одинаковую логику:
1. Проверить валидацию (все поля заполнены)
2. `task.status → in_progress`
3. Создать Session с `task_id = task.id`, `agent_id = task.starting_agent_id`
4. WS-соединение открывается, агент получает `task.description` как первое сообщение

---

## 5. API

### Tasks Router

```
GET    /api/tasks                          → list[TaskRead] (фильтр: product_id обязателен)
POST   /api/tasks                          → TaskRead (201)
GET    /api/tasks/{id}                     → TaskRead
PUT    /api/tasks/{id}                     → TaskRead
DELETE /api/tasks/{id}                     → 204
PATCH  /api/tasks/{id}/status              → TaskRead (смена статуса + валидация)
```

### Схемы

```python
class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    product_id: UUID | None = None
    team_id: UUID | None = None
    starting_agent_id: UUID | None = None

class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    product_id: UUID | None = None
    team_id: UUID | None = None
    starting_agent_id: UUID | None = None

class TaskStatusUpdate(BaseModel):
    status: str  # валидируется по разрешённым переходам

class TaskRead(BaseModel):
    id: UUID
    title: str
    description: str | None
    product_id: UUID | None
    team_id: UUID | None
    starting_agent_id: UUID | None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

---

## 6. Kanban Dashboard

### 6.1 Фильтры

Дашборд **не показывает задачи** без выбранного бизнеса и продукта.

| Фильтр | Обязательность | Описание |
|--------|---------------|----------|
| Business | Обязательный | Выбрать бизнес |
| Product | Обязательный | Выбрать продукт (зависит от выбранного бизнеса) |
| Team | Опциональный | Фильтр по команде |

При первом открытии — пустой экран с предложением выбрать бизнес и продукт.
После выбора — подтягиваются задачи `GET /api/tasks?product_id=...`.

### 6.2 Колонки

| Колонка | Default видимость | Условие появления |
|---------|-------------------|-------------------|
| `backlog` | Видна | Всегда |
| `in_progress` | Видна | Всегда |
| `awaiting_user` | Видна | Всегда |
| `done` | Скрыта | Показать через фильтр |
| `error` | Скрыта | Появляется автоматически если есть задачи со статусом error |

### 6.3 Пагинация

- Максимум 20 задач в одной колонке
- Кнопка "Показать ещё" в нижней части каждой колонки

### 6.4 Task Card

Минимальный состав карточки:
- Title
- Status badge
- Badge "⏳ Ждёт решения" если `status = awaiting_user`
- Команда (team name) если есть
- Кнопка "Начать" если `status = backlog` и все поля заполнены
- Клик по карточке → открывает Task Modal

### 6.5 Drag & Drop

Разрешённые переходы:

| Откуда | Куда | Условие |
|--------|------|---------|
| `backlog` | `in_progress` | Все поля задачи заполнены |
| `in_progress` | `done` | Без условий |
| `done` | `in_progress` | Без условий |
| `error` | `in_progress` | Без условий |

Все остальные переходы через drag — запрещены (карточка возвращается на место).

---

## 7. Task Modal

Открывается по клику на карточку.

### Вкладка "Детали"

Редактируемые поля:
- Title (text input)
- Description (textarea)
- Team (select из teams)
- Starting Agent (select из агентов выбранной команды)
- Status (read-only badge + кнопки действий)

Кнопка "Начать" если задача в `backlog` и валидна.

### Вкладка "Чаты"

Sidebar с табами агентов, у которых **есть сессии** с `task_id = task.id`.

Для каждой сессии:
- Если `session.status = in_progress` → полноценный WS-чат (send, stop, approve/reject)
- Если `session.status = done` → read-only история сообщений

approve/reject — в этой вкладке (не на отдельной ChatPage).

---

## 8. Устаревшие страницы

- **ChatPage** (`/chat/:sessionId`) — постепенно убирать. В рамках Tasks не удалять,
  но новые сессии открываются в Task Modal, не в ChatPage.
- **TeamPage** (`/teams/:id`) — заменяется Canvas (отдельная спека).

---

## 9. MCP Tools для Tasks (будущее)

System Agent сможет управлять задачами через MCP инструменты:
`create_task`, `list_tasks`, `start_task` — реализуются после стабилизации Tasks API.

---

## Порядок реализации

```
TASK-045: Tasks Backend
  — Task model, schemas, service, router
  — Session.task_id FK + migration
  — Agent.prompts field + migration
  — ws.py: workdir resolution (session → task → product)
  — ws.py: auto-update task.status на WS-событиях

TASK-046: Kanban Dashboard
  — Dashboard redesign: business+product фильтр (обязательный)
  — Kanban колонки, пагинация, drag & drop
  — Task Card компонент
  — api/tasks.ts, hooks/useTasks.ts, types

TASK-047: Task Modal
  — Task Modal компонент
  — Вкладка Детали (редактирование полей)
  — Вкладка Чаты (сессии задачи, WS-чат, approve/reject)
  — awaiting_user badge на карточке
```
