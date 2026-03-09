# Спецификация изменений: Business + Products (замена Workspaces)

## Контекст

Текущий функционал "Workspaces" (клонирование git-репозиториев) хранит данные только
на файловой системе — без модели в БД. Нужно заменить его на полноценные сущности:
**Business** (организация) и **Product** (продукт/направление, привязан к git-репозиторию).

Итоговая архитектура системы:

```
Business → Product → Task ←→ Team
                              (Task — вне scope этой спецификации)
```

Team остаётся независимой сущностью — не привязана к Business или Product напрямую.
Связь Team ↔ Product происходит через Task (Task содержит product_id + team_id).

---

## Что удаляем

| Файл | Причина |
|---|---|
| `api/app/routers/workspaces.py` | Заменяется routers/products.py |
| `web/src/components/WorkspacePanel.tsx` | Заменяется ProductPanel |
| `web/src/api/workspaces.ts` | Заменяется api/products.ts |
| `web/src/hooks/useWorkspaces.ts` | Заменяется hooks/useProducts.ts |

Из `api/app/main.py` убирается регистрация `workspaces` роутера.
Из `web/src/pages/Dashboard.tsx` убирается `<WorkspacePanel />`.

---

## Новые сущности

### Business

Организация верхнего уровня. У одного пользователя может быть несколько бизнесов.

**Таблица: `businesses`**

| Поле | Тип | Описание |
|---|---|---|
| id | UUID PK | |
| name | str(200), unique | Название организации |
| description | text, nullable | Описание |
| created_at | datetime | |

**Связи:**
- `Business.products[]` → один ко многим, cascade delete

---

### Product

Продукт/направление внутри бизнеса. Привязан к git-репозиторию.
Хранит путь на файловой системе сервера, куда склонирован репозиторий.

**Таблица: `products`**

| Поле | Тип | Описание |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK → businesses (CASCADE) | Владелец |
| name | str(200) | Название продукта |
| description | text, nullable | Описание |
| git_url | text, nullable | URL репозитория (https или ssh) |
| workspace_path | text | Путь на сервере после clone/init. Формат: `{settings.workspace_path}/products/{product.id}` |
| created_at | datetime | |

**Связи:**
- `Product.business` → Many-to-one
- `Product.sessions[]` → один ко многим (обратная связь от Session)

**Логика создания (git):**
- Если `git_url` указан → `git clone --depth 1 {git_url} {workspace_path}`
- Если `git_url` не указан → `git init {workspace_path}`
- Эта логика переезжает из `workspaces.py` в `product_service.py`
- `workspace_path` формируется как `{settings.workspace_path}/products/{product.id}` и сохраняется в БД

---

## Изменения существующих сущностей

### Session (расширение)

Добавляется необязательная привязка к продукту. Это позволяет агентам автоматически
получать `workdir` из продукта, а не из `agent.config`.

**Новое поле в таблице `sessions`:**

| Поле | Тип | Описание |
|---|---|---|
| product_id | UUID FK → products (SET NULL), nullable | Продукт, с которым работает сессия |

**Связь:** `Session.product` → Many-to-one (nullable)

**Логика workdir в `ws.py`:**
```
Сейчас:
  workdir = agent.config.get("workdir", "")

Станет:
  if session.product_id and session.product:
      workdir = session.product.workspace_path
  else:
      workdir = agent.config.get("workdir", "")  # обратная совместимость
```

Это неломающее изменение: существующие сессии без product_id продолжают работать
через `agent.config.workdir`.

---

## Backend — новые файлы

### `api/app/models/business.py`
ORM-модель Business. Связь `products` с cascade delete.

### `api/app/models/product.py`
ORM-модель Product. FK на businesses с CASCADE. Связи с Business и Session.

### `api/app/schemas/business.py`
```
BusinessCreate  : name, description?
BusinessUpdate  : name?, description?
BusinessRead    : id, name, description, created_at, products_count: int
```

### `api/app/schemas/product.py`
```
ProductCreate   : name, description?, git_url?, business_id
ProductUpdate   : name?, description?, git_url?
ProductRead     : id, business_id, name, description, git_url, workspace_path, created_at
```

### `api/app/services/business_service.py`
```
create_business(db, data: BusinessCreate) → Business
get_businesses(db) → list[Business]
get_business(db, business_id) → Business
delete_business(db, business_id) → None
```

### `api/app/services/product_service.py`
```
create_product(db, data: ProductCreate) → Product
  - вычисляет workspace_path = settings.workspace_path + "/products/" + str(new_id)
  - сохраняет запись в БД
  - запускает git clone / git init через asyncio.create_subprocess_exec
  - обновляет workspace_path если нужно
get_products(db, business_id) → list[Product]
get_product(db, product_id) → Product
delete_product(db, product_id) → None
```

### `api/app/routers/businesses.py`
```
GET    /api/businesses            → list[BusinessRead]
POST   /api/businesses            → BusinessRead (201)
GET    /api/businesses/{id}       → BusinessRead
DELETE /api/businesses/{id}       → 204
```

### `api/app/routers/products.py`
```
GET    /api/businesses/{business_id}/products   → list[ProductRead]
POST   /api/businesses/{business_id}/products   → ProductRead (201)
GET    /api/products/{id}                       → ProductRead
DELETE /api/products/{id}                       → 204
```

---

## Backend — изменения существующих файлов

### `api/app/models/__init__.py`
Добавить импорты: `from app.models.business import Business` и `from app.models.product import Product`.
Добавить в `__all__`.

### `api/app/models/session.py`
Добавить поле `product_id` (UUID, nullable FK → products ON DELETE SET NULL).
Добавить relationship `product = relationship("Product", back_populates="sessions")`.

### `api/app/services/session_service.py`
В функции `get_session()` добавить `selectinload(Session.product)` к запросу,
чтобы `ws.py` мог читать `session.product.workspace_path` без N+1 запросов.

### `api/app/routers/ws.py`
Обновить строку 58: логика выбора `workdir` (см. раздел "Изменения существующих сущностей").

### `api/app/main.py`
- Убрать: импорт `workspaces`, `app.include_router(workspaces.router, ...)`
- Добавить: импорт `businesses`, `products` и их `include_router`

---

## Миграция БД

```bash
cd api && alembic revision --autogenerate -m "add businesses and products, session product_id"
alembic upgrade head
```

Миграция создаёт:
- Таблицу `businesses`
- Таблицу `products`
- Колонку `sessions.product_id` (nullable FK)

---

## Frontend — новые файлы

### `web/src/api/businesses.ts`
```typescript
interface Business { id, name, description, created_at }
interface BusinessCreate { name, description? }

getBusinesses(): Promise<Business[]>
createBusiness(data: BusinessCreate): Promise<Business>
deleteBusiness(id: string): Promise<void>
```

### `web/src/api/products.ts`
```typescript
interface Product { id, business_id, name, description, git_url, workspace_path, created_at }
interface ProductCreate { name, description?, git_url?, business_id }

getProducts(businessId: string): Promise<Product[]>
createProduct(data: ProductCreate): Promise<Product>
deleteProduct(id: string): Promise<void>
```

### `web/src/hooks/useBusinesses.ts`
```typescript
useBusinesses()        → useQuery
useCreateBusiness()    → useMutation (invalidates businesses key)
useDeleteBusiness()    → useMutation (invalidates businesses key)
```

### `web/src/hooks/useProducts.ts`
```typescript
useProducts(businessId: string)  → useQuery
useCreateProduct()               → useMutation (invalidates products key)
useDeleteProduct()               → useMutation (invalidates products key)
```

### `web/src/components/ProductPanel.tsx`
Заменяет `WorkspacePanel`. Отображает двухуровневую структуру:

```
[+ New Business]

▼ Business: "My Company"
    Product: "SaaS App"  — github.com/org/saas  — /workspace/products/abc
    Product: "Mobile"    — github.com/org/mobile — /workspace/products/def
    [+ Add Product]

▼ Business: "Side Project"
    (нет продуктов)
    [+ Add Product]
```

Форма создания бизнеса: name, description.
Форма создания продукта: name, git_url (optional). business_id берётся из контекста.

---

## Frontend — изменения существующих файлов

### `web/src/pages/Dashboard.tsx`
- Убрать: `import { WorkspacePanel }`, `<WorkspacePanel />`
- Добавить: `import { ProductPanel }`, `<ProductPanel />`

### `web/src/types/index.ts`
Добавить интерфейсы `Business` и `Product` (либо реэкспортировать из api/).

---

## Что НЕ входит в эту спецификацию

- Сущность `Task` (задача на доске) — отдельная спецификация
- Связь Task → Team → Product — отдельная спецификация
- Кнопка "Начать" и запуск агентов из задачи — отдельная спецификация
- Kanban-доска — отдельная спецификация
- Страница Business и Product (отдельные роуты) — отдельная спецификация

---

## Порядок реализации (предлагаемое разбиение на задачи)

```
Задача A: Business + Product backend
  - models, schemas, services, routers
  - удалить workspaces.py
  - обновить main.py, models/__init__.py
  - миграция БД

Задача B: Session → Product связь
  - добавить product_id в Session model
  - session_service selectinload
  - ws.py workdir resolution
  - миграция (можно объединить с A)

Задача C: Frontend замена Workspaces → ProductPanel
  - api/businesses.ts, api/products.ts
  - hooks/useBusinesses.ts, hooks/useProducts.ts
  - components/ProductPanel.tsx
  - обновить Dashboard.tsx
  - удалить workspace файлы
```
