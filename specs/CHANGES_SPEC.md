# Спецификация изменений: Business + Products + System Agent

## Контекст

Заменяем "Workspaces" (git clone без модели в БД) на полноценные сущности:
**Business** (организация) и **Product** (продукт с git-репозиторием).
Добавляем **System Agent** — специальный агент для управления платформой через
глобальный чат-виджет.

Итоговая архитектура системы:

```
Business → Product → Task ←→ Team
                      ↑
                   Session (task_id)

System Agent (лидер Admin-команды) → Global Sessions (task_id = NULL)
```

**Session.product_id не добавляется в этой спецификации.** Workdir будет
резолвиться через `session → task → product` когда появится сущность Task.

---

## Что удаляем

| Файл | Причина |
|---|---|
| `api/app/routers/workspaces.py` | Заменяется routers/products.py |
| `web/src/components/WorkspacePanel.tsx` | Заменяется страницами Business/Product |
| `web/src/api/workspaces.ts` | Заменяется api/products.ts |
| `web/src/hooks/useWorkspaces.ts` | Заменяется hooks/useProducts.ts |

Из `api/app/main.py` убирается регистрация `workspaces` роутера.
Из `web/src/pages/Dashboard.tsx` убирается `<WorkspacePanel />`.

---

## Новые сущности

### Business

Организация верхнего уровня.

**Таблица: `businesses`**

| Поле | Тип | Описание |
|---|---|---|
| id | UUID PK | |
| name | str(200), unique globally | Название (для будущего multi-user: unique per user) |
| description | text, nullable | Описание |
| created_at | datetime | |

**Связи:**
- `Business.products[]` → один ко многим, cascade delete (включая файлы)

**Заметка для будущего:** когда появятся Users, добавить `user_id FK` и
изменить unique constraint на `unique(user_id, name)`.

---

### Product

Продукт/направление внутри бизнеса. Привязан к git-репозиторию.

**Таблица: `products`**

| Поле | Тип | Описание |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK → businesses (CASCADE) | Владелец |
| name | str(200) | unique в рамках одного Business |
| description | text, nullable | Описание |
| git_url | text, nullable | URL репозитория (https или ssh) |
| workspace_path | text | Путь на сервере. Формат: `{settings.workspace_path}/products/{product.id}` |
| status | str | `pending` / `cloning` / `ready` / `error` |
| clone_error | text, nullable | Сообщение об ошибке клонирования |
| created_at | datetime | |

**Уникальность:** `unique(business_id, name)` — имя уникально внутри бизнеса.

**Связи:**
- `Product.business` → Many-to-one
- `Product.sessions[]` → один ко многим (обратная связь от Session, для будущего)

---

### Agent (расширение)

Добавляется флаг системного агента.

**Новое поле в таблице `agents`:**

| Поле | Тип | Описание |
|---|---|---|
| is_system | bool, default false | Флаг System Agent (лидер Admin-команды) |

---

## Логика клонирования (manual, двухшаговая)

**Шаг 1: POST /api/businesses/{business_id}/products**
- Создаёт запись в БД со `status: "pending"`
- Вычисляет `workspace_path = settings.workspace_path + "/products/" + str(id)`
- Создаёт директорию `workspace_path`
- НЕ запускает git

**Шаг 2: POST /api/products/{id}/clone** (кнопка "Клонировать")
- Переводит `status → "cloning"`
- Если `git_url` не указан → кнопка задизейблена на frontend, endpoint возвращает 400
- Если `status == "cloning"` → 409 Conflict
- Если `status == "error"` → удаляет содержимое директории, клонирует заново
- Запускает `git clone --depth 1 {git_url} {workspace_path}` или `git init {workspace_path}`
- Таймаут: `settings.AC_CLONE_TIMEOUT_SECONDS` (default: 300)
- При успехе: `status → "ready"`, `clone_error = None`
- При ошибке: `status → "error"`, `clone_error = stderr`

**Frontend polling:** после POST /clone frontend делает `refetchInterval: 2000`
на GET /api/products/{id} пока `status` не станет `"ready"` или `"error"`.

---

## Логика удаления

### DELETE /api/products/{id}

```
1. Проверить наличие активных сессий (status = "in_progress"), использующих
   этот продукт (пока через будущий task_id — сейчас просто предупреждение на UI)
2. Удалить запись из БД
3. shutil.rmtree(workspace_path, ignore_errors=True)  — не блокирует ответ при ошибке
4. Вернуть 204
```

### DELETE /api/businesses/{id}

```
1. Проверить: есть ли продукты у бизнеса
2. Если есть — вернуть список на frontend для предупреждения
3. Frontend показывает: "Будет удалено N продуктов и их репозитории. Продолжить?"
4. При подтверждении: frontend снова шлёт DELETE с query param `?force=true`
5. Backend: get_products → для каждого product: удалить файлы → удалить из БД
6. Удалить Business
```

---

## Backend — новые файлы

### `api/app/models/business.py`
ORM-модель Business. Связь `products` с cascade delete.

### `api/app/models/product.py`
ORM-модель Product. FK на businesses с CASCADE. Unique constraint на (business_id, name).
Поля status, clone_error. Связь с Session (back_populates="sessions", для будущего).

### `api/app/schemas/business.py`
```
BusinessCreate  : name, description?
BusinessUpdate  : name?, description?
BusinessRead    : id, name, description, created_at, products_count: int
```
`products_count` вычисляется через `func.count` subquery в сервисе.

### `api/app/schemas/product.py`
```
ProductCreate   : name, description?, git_url?, business_id
ProductUpdate   : name?, description?, git_url?
ProductRead     : id, business_id, name, description, git_url, workspace_path,
                  status, clone_error, created_at
```

### `api/app/services/business_service.py`
```
create_business(db, data: BusinessCreate) → Business
get_businesses(db) → list[Business] (с products_count)
get_business(db, business_id) → Business
update_business(db, business_id, data: BusinessUpdate) → Business
delete_business(db, business_id, force: bool) → None
  — если force=False и есть продукты → raise ConflictError с count
  — если force=True → удалить продукты (файлы + БД) → удалить бизнес
```

### `api/app/services/product_service.py`
```
create_product(db, data: ProductCreate) → Product
  — workspace_path = settings.workspace_path + "/products/" + str(id)
  — os.makedirs(workspace_path, exist_ok=True)
  — status = "pending"
get_products(db, business_id) → list[Product]
get_product(db, product_id) → Product
update_product(db, product_id, data: ProductUpdate) → Product
delete_product(db, product_id) → None
  — shutil.rmtree(workspace_path, ignore_errors=True)
clone_product(db, product_id) → Product
  — проверки статуса (409 если "cloning", 400 если нет git_url)
  — если "error": rmtree + makedirs (чистый старт)
  — status → "cloning", commit
  — asyncio.wait_for(subprocess, timeout=AC_CLONE_TIMEOUT_SECONDS)
  — обновить status → "ready" или "error"
```

### `api/app/routers/businesses.py`
```
GET    /api/businesses               → list[BusinessRead]
POST   /api/businesses               → BusinessRead (201)
GET    /api/businesses/{id}          → BusinessRead
PUT    /api/businesses/{id}          → BusinessRead
DELETE /api/businesses/{id}          → 204 (или 409 с products_count если нет ?force)
DELETE /api/businesses/{id}?force=true → 204
```

### `api/app/routers/products.py`
```
GET    /api/businesses/{business_id}/products   → list[ProductRead]
POST   /api/businesses/{business_id}/products   → ProductRead (201)
GET    /api/products/{id}                       → ProductRead
PUT    /api/products/{id}                       → ProductRead
DELETE /api/products/{id}                       → 204
POST   /api/products/{id}/clone                 → ProductRead
```

---

## Backend — изменения существующих файлов

### `api/app/models/agent.py`
Добавить поле `is_system: bool = Column(Boolean, default=False)`.

### `api/app/models/__init__.py`
Добавить импорты Business и Product. Добавить в `__all__`.

### `api/app/main.py`
- Убрать: импорт `workspaces`, `app.include_router(workspaces.router, ...)`
- Добавить: импорт `businesses`, `products` и их `include_router`
- Добавить в lifespan: `await seed_system_agent(db)` — создаёт System Agent если отсутствует

### `api/app/config.py`
Добавить: `AC_CLONE_TIMEOUT_SECONDS: int = 300`

### `api/app/schemas/agent.py`
Добавить поле `is_system: bool = False` в `AgentRead` и `AgentCreate`.

### `api/app/routers/agents.py`
Добавить endpoint: `GET /api/agents/system → AgentRead`

---

## System Agent

### Концепция

System Agent — специальный агент с `is_system=True`. Создаётся в lifespan
автоматически (`seed_system_agent`). Если удалён из БД — пересоздаётся при
следующем старте приложения. Является лидером будущей "Admin" команды.

### seed_system_agent (новый файл: `api/app/services/system_agent_service.py`)
```python
async def seed_system_agent(db: AsyncSession) -> Agent:
    existing = await db.execute(select(Agent).where(Agent.is_system == True))
    if existing.scalar_one_or_none():
        return existing
    agent = Agent(
        name="Assistant",
        is_system=True,
        system_prompt=SYSTEM_AGENT_PROMPT,  # константа в этом файле
        config={"allowed_tools": ["Bash", "computer"]}
    )
    db.add(agent)
    await db.commit()
    return agent
```

### GET /api/agents/system
Возвращает System Agent. Если не существует (race condition) — создаёт и возвращает.
Frontend использует для получения agent_id перед созданием Global Chat сессии.

### Использование OAuth
System Agent использует тот же OAuth token, что и остальные агенты.
Global Chat Widget задизейблен и показывает "Требуется авторизация" пока
`GET /api/auth/status` не возвращает `authenticated: true`.

---

## Миграция БД

```bash
cd api && alembic revision --autogenerate -m "add businesses, products, agent is_system"
alembic upgrade head
```

Миграция создаёт:
- Таблицу `businesses`
- Таблицу `products` (с unique(business_id, name), status, clone_error)
- Колонку `agents.is_system` (nullable → default false)

---

## Frontend — новые страницы и файлы

### Страницы (новые роуты)
```
/businesses                    → BusinessListPage
/businesses/:businessId        → BusinessPage (список Products внутри)
```

Dashboard убирает WorkspacePanel и добавляет ссылку/виджет на /businesses.

### `web/src/api/businesses.ts`
```typescript
getBusinesses(): Promise<BusinessRead[]>
getBusiness(id: string): Promise<BusinessRead>
createBusiness(data: BusinessCreate): Promise<BusinessRead>
updateBusiness(id: string, data: BusinessUpdate): Promise<BusinessRead>
deleteBusiness(id: string, force?: boolean): Promise<void>
```

### `web/src/api/products.ts`
```typescript
getProducts(businessId: string): Promise<ProductRead[]>
getProduct(id: string): Promise<ProductRead>
createProduct(data: ProductCreate): Promise<ProductRead>
updateProduct(id: string, data: ProductUpdate): Promise<ProductRead>
deleteProduct(id: string): Promise<void>
cloneProduct(id: string): Promise<ProductRead>
```

### `web/src/hooks/useBusinesses.ts`
```typescript
useBusinesses()                → useQuery(["businesses"])
useBusiness(id)                → useQuery(["businesses", id])
useCreateBusiness()            → useMutation (invalidates ["businesses"])
useUpdateBusiness()            → useMutation (invalidates ["businesses", id])
useDeleteBusiness()            → useMutation (invalidates ["businesses"])
```

### `web/src/hooks/useProducts.ts`
```typescript
useProducts(businessId)        → useQuery(["products", businessId])
useProduct(id, options?)       → useQuery(["products", "detail", id],
                                          { refetchInterval: polling? 2000 : false })
useCreateProduct()             → useMutation (invalidates ["products", businessId])
useUpdateProduct()             → useMutation (invalidates ["products", "detail", id])
useDeleteProduct()             → useMutation (invalidates ["products", businessId])
useCloneProduct()              → useMutation → запускает polling через useProduct
```

### `web/src/components/GlobalChatWidget.tsx`
Фиксированный bottom-right чат-виджет. Присутствует на ВСЕХ страницах.

```
Состояния:
- Задизейблен (не авторизован) — показывает "Требуется авторизация в Claude"
- Свёрнут — кнопка чата в углу
- Развёрнут — окно чата (~400x600px)

Функциональность:
- Кнопка "Очистить контекст" (удаляет сообщения текущей сессии)
- История сохраняется между перезагрузками (session_id в localStorage)
- Если session_id из localStorage не найден в БД → создаётся новая сессия молча
- Использует useChat hook с System Agent session_id
```

### `web/src/hooks/useSystemAgent.ts`
```typescript
useSystemAgent()  →  { sessionId, isLoading, isDisabled }
  - GET /api/agents/system → получить system agent_id
  - GET /api/sessions?agent_id=system или localStorage → session_id
  - Если нет сессии → POST /api/sessions создать
  - isDisabled = true если не авторизован
```

---

## Frontend — изменения существующих файлов

### `web/src/App.tsx`
- Добавить роуты: `/businesses`, `/businesses/:businessId`
- Добавить `<GlobalChatWidget />` вне `<Routes>` (рендерится всегда)

### `web/src/pages/Dashboard.tsx`
- Убрать: `import { WorkspacePanel }`, `<WorkspacePanel />`
- Добавить: ссылку / кнопку "Бизнесы и продукты" → `/businesses`

### `web/src/types/index.ts`
Добавить интерфейсы:
```typescript
interface Business { id, name, description, created_at, products_count }
interface BusinessCreate { name, description? }
interface BusinessUpdate { name?, description? }
interface Product { id, business_id, name, description, git_url,
                    workspace_path, status, clone_error, created_at }
interface ProductCreate { name, description?, git_url?, business_id }
interface ProductUpdate { name?, description?, git_url? }
```

---

## Что НЕ входит в эту спецификацию

- Session.product_id / Session.task_id — появятся с Tasks
- Сущность Task — отдельная спецификация
- Team Leader / Admin Team — отдельная спецификация
- MCP Platform Tools (create_task, create_agent через System Agent) — TASK-044
- Kanban-доска — отдельная спецификация
- Авторизация / multi-user — будущее

---

## Порядок реализации

```
TASK-041: Business + Product backend
  - models, schemas, services, routers
  - system_agent_service (seed)
  - удалить workspaces.py
  - обновить main.py, models/__init__.py, config.py
  - миграция БД

TASK-042: Business + Product frontend
  - pages: BusinessListPage, BusinessPage
  - api, hooks, components
  - GlobalChatWidget + useSystemAgent
  - обновить App.tsx, Dashboard.tsx
  - удалить workspace файлы

TASK-043: MCP Platform Tools
  - расширить api/mcp/server.py
  - api/mcp/tools/platform.py
```
