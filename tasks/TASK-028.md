---
id: TASK-028
title: "Bugfix: Frontend — useChat refs, cache invalidation, error display"
type: bugfix
status: backlog
assigned_to: developer
priority: 28
feature: "frontend-fixes"
depends_on: []
---

# TASK-028: Frontend — исправление багов UI

## Контекст

Архитектурный анализ выявил 6 проблем во фронтенде: stale refs при reconnect (6.34), zombie streaming элемент (6.31), tool_use/tool_result не вызывают re-render (6.2, 6.39), cache invalidation bypass (6.66), code duplication (6.67), silent delete errors (6.68).

## Баги

### BUG-1 [BUG] — Stale pending refs при reconnect (6.34)

**Файл:** `web/src/hooks/useChat.ts:287-294`

```tsx
return () => {
  if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
  if (wsRef.current) {
    wsRef.current.close();
    wsRef.current = null;
  }
  // ⚠ pendingTextRef, pendingToolsRef, pendingSubAgentRef НЕ сбрасываются
};
```

При WS disconnect и reconnect `pendingTextRef.current` содержит текст от предыдущего стриминга. Новый `assistant_text` конкатенируется с ним → дублированный/мусорный текст.

**Исправление:** Добавить сброс всех pending refs в cleanup:
```tsx
pendingTextRef.current = "";
pendingToolsRef.current = [];
pendingSubAgentRef.current = null;
```

Также добавить сброс при начале reconnect (перед `connect()`).

### BUG-2 [UX] — Zombie `__streaming__` элемент при WS disconnect (6.31)

**Файл:** `web/src/hooks/useChat.ts:69`

Если WS disconnect происходит между `assistant_text` и `done`, элемент с `id: "__streaming__"` остаётся в items навсегда. При reconnect не очищается.

**Исправление:** При disconnect/reconnect — удалять `__streaming__` из items:
```tsx
setItems(prev => prev.filter(item => item.id !== "__streaming__"));
```

### BUG-3 [UX] — tool_use/tool_result/sub_agent_tool_use/sub_agent_tool_result не вызывают re-render (6.2, 6.39)

**Файл:** `web/src/hooks/useChat.ts:74-87, 179-195`

```tsx
case "tool_use":
  pendingToolsRef.current.push({ tool_name: event.tool_name, tool_input: event.tool_input });
  break;  // ← нет setItems

case "tool_result": {
  const lastTool = pendingToolsRef.current[pendingToolsRef.current.length - 1];
  if (lastTool) {
    lastTool.result = event.content;
  }
  break;  // ← нет setItems
}
```

Мутация refs без `setItems()`. Tool-вызовы и результаты не отображаются до `done`/`handoff_done`. При длительных tool execution (10+ секунд) пользователь не видит что агент работает.

**Исправление:** После каждой мутации ref вызывать `setItems()` с обновлённым `__streaming__` элементом для real-time rendering. Создать helper-функцию для обновления streaming item:

```tsx
function updateStreamingItem() {
  setItems(prev => {
    const idx = prev.findIndex(i => i.id === "__streaming__");
    if (idx === -1) return prev;
    const updated = [...prev];
    updated[idx] = {
      ...updated[idx],
      content: pendingTextRef.current,
      toolUses: [...pendingToolsRef.current],
    };
    return updated;
  });
}
```

Аналогично для sub_agent_tool_use и sub_agent_tool_result.

### BUG-4 [BUG] — AgentCard обходит useCreateSession — кэш не инвалидируется (6.66)

**Файл:** `web/src/components/AgentCard.tsx:4, 19`

```tsx
import { createSession } from "../api/sessions";  // прямой API-вызов
const session = await createSession(agent.id);     // без хука
```

Прямой вызов минует `useCreateSession` хук, который делает `invalidateQueries({ queryKey: SESSIONS_KEY })`. После создания сессии через AgentCard, SessionList не знает о новой сессии до следующего refetchInterval (10 секунд).

**Исправление:** Заменить прямой вызов на хук `useCreateSession()` из `useSessions.ts` (как в `QuickStartChat.tsx`).

### BUG-5 [CODE DUPLICATION] — SessionList дублирует useQuery из useSessions (6.67)

**Файл:** `web/src/components/SessionList.tsx:72-76`

```tsx
const { data: sessions, isLoading } = useQuery({
  queryKey: ["sessions"],
  queryFn: getSessions,
  refetchInterval: 10_000,
});
```

Дублирует хук `useSessions()` из `hooks/useSessions.ts`. При изменении queryKey или refetchInterval в одном месте второе может разойтись.

**Исправление:** Заменить inline `useQuery` на `useSessions()`.

### BUG-6 [UX] — Ошибки delete-мутаций не показываются (6.68)

**Файлы:** `web/src/pages/Dashboard.tsx:32-36`, `web/src/pages/TeamPage.tsx:38-42`

```tsx
function handleDelete(id: string) {
  if (window.confirm("Delete this team?")) {
    deleteTeam.mutate(id);  // нет onError
  }
}
```

При ошибке удаления пользователь не видит feedback. Мутация тихо проваливается.

**Исправление:** Добавить `onError` callback:
```tsx
deleteTeam.mutate(id, {
  onError: (err: Error) => alert(err.message),
});
```

Тот же паттерн для `deleteAgent.mutate()` и `deleteLink.mutate()` в TeamPage.

## Файлы для чтения

- `web/src/hooks/useChat.ts` — pending refs, handleEvent, cleanup
- `web/src/hooks/useChat.test.ts` — существующие тесты
- `web/src/hooks/useSessions.ts` — `useSessions()`, `useCreateSession()`
- `web/src/components/AgentCard.tsx` — прямой API-вызов
- `web/src/components/QuickStartChat.tsx` — правильный паттерн с хуком
- `web/src/components/SessionList.tsx` — дублированный useQuery
- `web/src/pages/Dashboard.tsx` — handleDelete
- `web/src/pages/TeamPage.tsx` — handleDelete для agents и links

## Acceptance Criteria

- [ ] При WS reconnect pending refs сбрасываются (нет дублированного текста)
- [ ] При WS disconnect `__streaming__` элемент удаляется из items
- [ ] `tool_use` и `tool_result` вызывают re-render в реальном времени (не ждут `done`)
- [ ] `sub_agent_tool_use` и `sub_agent_tool_result` аналогично вызывают re-render
- [ ] AgentCard использует `useCreateSession()` — кэш sessions инвалидируется
- [ ] SessionList использует `useSessions()` вместо inline useQuery
- [ ] Ошибки delete-мутаций показывают alert пользователю
- [ ] TypeScript build чистый (`npm run build`)
- [ ] Тесты проходят (`npm test`)
- [ ] `npm run lint` без ошибок

## Ограничения

- Не менять логику WebSocket-соединения (порядок событий, reconnect strategy)
- Не менять компоненты ChatMessage, ChatWindow
- Не добавлять новые зависимости (toast library и т.п.) — использовать `alert()` для ошибок
