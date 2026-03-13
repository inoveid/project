import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTaskSessions } from '../../hooks/useTasks';
import { getSession, stopSession } from '../../api/sessions';
import { useChat } from '../../hooks/useChat';
import { ChatWindow } from '../ChatWindow';
import type { Task, Session, SessionListItem, ChatItem } from '../../types';
import { isHandoffItem } from '../../types';
import { ApprovalCard } from '../ApprovalCard';

interface TaskChatsTabProps {
  task: Task;
}

export function TaskChatsTab({ task }: TaskChatsTabProps) {
  const queryClient = useQueryClient();
  const { data: sessions, isLoading } = useTaskSessions(task.id, task.status);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const prevSessionIdsRef = useRef<Set<string>>(new Set());
  const pendingSwithToAgentRef = useRef<string | null>(null);

  // Main session (oldest, depth=0) — WS always connected at this level
  const mainSessionId = sessions?.[sessions.length - 1]?.id ?? '';

  const { data: mainSession } = useQuery({
    queryKey: ['session', mainSessionId],
    queryFn: () => getSession(mainSessionId),
    enabled: Boolean(mainSessionId),
  });

  const mainLoaded = Boolean(mainSession);
  const mainActive = mainSession?.status === 'active';

  // This hook keeps the main session WS alive regardless of which chat is selected
  const mainChat = useChat(
    mainSessionId,
    mainSession?.messages ?? [],
    mainLoaded && mainActive,
  );

  // Auto-switch to active session on approval
  useEffect(() => {
    if (task.status === 'awaiting_user' && sessions?.length) {
      const activeSession = sessions.find((s) => s.status === 'active');
      if (activeSession && activeSession.id !== selectedId) {
        setSelectedId(activeSession.id);
      }
    }
  }, [task.status, sessions, selectedId]);

  // Auto-switch to new session when it appears OR when pending switch resolves
  useEffect(() => {
    if (!sessions?.length) return;
    const currentIds = new Set(sessions.map((s) => s.id));
    const prevIds = prevSessionIdsRef.current;

    // Check pending agent switch first (after approve with session reuse)
    if (pendingSwithToAgentRef.current) {
      const target = sessions.find(
        (s) => s.agent_name === pendingSwithToAgentRef.current && s.status === 'active',
      );
      if (target) {
        setSelectedId(target.id);
        pendingSwithToAgentRef.current = null;
      }
    } else if (prevIds.size > 0) {
      // Detect truly new sessions
      for (const id of currentIds) {
        if (!prevIds.has(id)) {
          setSelectedId(id);
          break;
        }
      }
    }

    prevSessionIdsRef.current = currentIds;
  }, [sessions]);

  // Approve / Reject — always goes through main session WS
  function handleApprove() {
    // Determine which agent we're handing off to, find their session to switch
    const toAgentName = effectiveApproval?.toAgent;
    if (toAgentName && sessions) {
      const targetSession = sessions.find((s) => s.agent_name === toAgentName && s.status === 'active');
      if (targetSession) {
        setSelectedId(targetSession.id);
      } else {
        // Session might not exist yet (will be created) — set a flag to switch on next sessions update
        pendingSwithToAgentRef.current = toAgentName;
      }
    }
    mainChat.approveHandoff();
    void queryClient.invalidateQueries({ queryKey: ['tasks', 'detail', task.id] });
    void queryClient.invalidateQueries({ queryKey: ['sessions', 'by-task', task.id] });
  }

  function handleReject() {
    mainChat.rejectHandoff();
    void queryClient.invalidateQueries({ queryKey: ['tasks', 'detail', task.id] });
  }

  // Extract real-time items for the selected sub-session from main WS
  const activeId = selectedId ?? mainSessionId;
  const isViewingMain = activeId === mainSessionId;
  const selectedAgentName = sessions?.find((s) => s.id === activeId)?.agent_name ?? '';
  const subAgentRealtimeItems = useMemo(() => {
    if (isViewingMain || !selectedAgentName) return [];
    return mainChat.items.filter((item) => {
      if (!isHandoffItem(item)) return false;
      if (item.id === '__sub_agent_streaming__' && item.agentName === selectedAgentName) return true;
      if (item.id === '__activity__' && item.agentName === selectedAgentName) return true;
      return false;
    });
  }, [isViewingMain, selectedAgentName, mainChat.items]);

  if (isLoading) {
    return <p className="text-gray-400 text-sm p-6">Загрузка сессий...</p>;
  }

  if (!sessions || sessions.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-gray-400 text-sm">Задача ещё не запущена</p>
      </div>
    );
  }

  // Track which agent is currently working (from WS events)
  const activeAgentFromWs = (() => {
    // If status is streaming/thinking, the current active agent is working
    // Check the last handoff item to know which agent that is
    if (mainChat.status === 'typing' || mainChat.status === 'tool') {
      const lastHandoff = [...mainChat.items]
        .reverse()
        .find((i) => isHandoffItem(i) && i.itemType === 'handoff_start');
      if (lastHandoff && isHandoffItem(lastHandoff)) return lastHandoff.toAgent ?? null;
    }
    return null;
  })();

  // Approval — derived from main session WS (always connected)
  const approvalFromItems = (() => {
    const last = mainChat.items
      .filter((i) => isHandoffItem(i) && i.itemType === 'approval_required')
      .pop();
    if (last && isHandoffItem(last) && last.fromAgent && last.toAgent) {
      return { fromAgent: last.fromAgent, toAgent: last.toAgent, task: last.content };
    }
    return null;
  })();
  const effectiveApproval = mainChat.pendingApproval || approvalFromItems;
  // Show approval from WS event immediately OR from task status (after refetch)
  const showApproval = (task.status === 'awaiting_user' || mainChat.status === 'awaiting_approval') && mainActive;

  return (
    <div className="flex flex-1 min-h-0">
      <SessionSidebar
        sessions={sessions}
        activeId={activeId}
        taskStatus={task.status}
        activeAgentName={activeAgentFromWs}
        onSelect={setSelectedId}
      />

      <div className="flex flex-1 flex-col min-w-0">
        {isViewingMain ? (
          <MainSessionView session={mainSession} chat={mainChat} task={task} />
        ) : (
          <SubSessionView
            sessionId={activeId}
            task={task}
            realtimeItems={subAgentRealtimeItems}
          />
        )}

        {/* Approval card — always visible regardless of selected session */}
        {showApproval && (
          <ApprovalCard
            approval={effectiveApproval || { fromAgent: 'Агент', toAgent: '...', task: 'Ожидает вашего решения' }}
            onApprove={handleApprove}
            onReject={handleReject}
          />
        )}
      </div>
    </div>
  );
}

// ── Session sidebar ──────────────────────────────────────────────────────────

function SessionSidebar({
  sessions,
  activeId,
  taskStatus,
  activeAgentName,
  onSelect,
}: {
  sessions: SessionListItem[];
  activeId: string;
  taskStatus: Task['status'];
  activeAgentName: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="w-[250px] border-r overflow-y-auto bg-gray-50">
      {sessions.map((s) => {
        const isActive = s.id === activeId;
        const statusIcon = s.status === 'active' ? '🟢' : s.status === 'stopped' ? '✅' : '🔴';
        const showAwaitingBadge =
          s.status === 'active' && taskStatus === 'awaiting_user';

        return (
          <button
            key={s.id}
            type="button"
            onClick={() => onSelect(s.id)}
            className={`w-full text-left px-3 py-2.5 border-b border-gray-200 text-sm ${
              isActive ? 'bg-white font-medium' : 'hover:bg-gray-100'
            }`}
          >
            <span className="flex items-center gap-2">
              <span>{statusIcon}</span>
              <span className="truncate flex-1">{s.agent_name}</span>
              {showAwaitingBadge && (
                <span className="text-xs bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded-full">
                  ⏳
                </span>
              )}
              {!showAwaitingBadge && s.agent_name === activeAgentName && (
                <span className="text-[10px] text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded-full shrink-0">
                  работает
                </span>
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ── Main session view (uses shared useChat from parent) ─────────────────────

function MainSessionView({
  session,
  chat,
  task,
}: {
  session: Session | undefined;
  chat: ReturnType<typeof useChat>;
  task: Task;
}) {
  const queryClient = useQueryClient();
  const isActive = session?.status === 'active';

  async function handleStop() {
    chat.stopAgent();
    if (session?.id) {
      await stopSession(session.id);
      void queryClient.invalidateQueries({ queryKey: ['sessions'] });
      void queryClient.invalidateQueries({ queryKey: ['sessions', 'by-task', task.id] });
    }
  }

  const canSend = chat.status === 'connected' && isActive && task.status !== 'awaiting_user';

  return (
    <>
      <div className="flex items-center justify-between border-b px-4 py-2 bg-white">
        <span className="text-xs text-gray-500">Главная сессия</span>
        {isActive && (
          <button
            onClick={() => void handleStop()}
            disabled={chat.status === 'disconnected' || chat.status === 'idle'}
            className="rounded border border-red-300 px-3 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-50"
          >
            Stop
          </button>
        )}
      </div>

      {chat.error && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-2 text-sm text-red-600">
          {chat.error}
        </div>
      )}

      <ChatWindow items={isActive ? chat.items : (session?.messages ?? [])} />

      {canSend && (
        <ChatInput onSend={chat.sendMessage} disabled={!canSend} />
      )}
    </>
  );
}

// ── Sub-session view (DB messages with polling) ─────────────────────────────

function SubSessionView({
  sessionId,
  task,
  realtimeItems = [],
}: {
  sessionId: string;
  task: Task;
  realtimeItems?: ChatItem[];
}) {
  const isTaskRunning = task.status === 'in_progress';

  const { data: session, isLoading, error } = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => getSession(sessionId),
    enabled: Boolean(sessionId),
    refetchInterval: isTaskRunning ? 2000 : false,
  });

  const hasRealtimeActivity = realtimeItems.length > 0;

  // Combine DB messages with real-time streaming overlay (must be before early returns)
  const items = useMemo(() => {
    const dbMessages = session?.messages ?? [];
    if (!hasRealtimeActivity) return dbMessages;
    return [...dbMessages, ...realtimeItems];
  }, [session?.messages, realtimeItems, hasRealtimeActivity]);

  if (isLoading) {
    return <p className="text-gray-400 text-sm p-4 flex-1">Загрузка чата...</p>;
  }

  if (error) {
    return <p className="text-red-600 text-sm p-4 flex-1">Ошибка: {error.message}</p>;
  }

  const isActive = session?.status === 'active';

  return (
    <>
      <div className="flex items-center justify-between border-b px-4 py-2 bg-white">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">{sessionId.slice(0, 8)}...</span>
          {(hasRealtimeActivity || (isActive && isTaskRunning)) && (
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
              <span className="text-xs text-gray-500">Работает...</span>
            </span>
          )}
        </div>
      </div>

      <ChatWindow items={items} />
    </>
  );
}

// ── Chat input ───────────────────────────────────────────────────────────────

function ChatInput({
  onSend,
  disabled,
}: {
  onSend: (content: string) => void;
  disabled: boolean;
}) {
  const [text, setText] = useState('');

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText('');
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 border-t p-3 bg-white">
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Написать сообщение..."
        disabled={disabled}
        className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:bg-gray-100"
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Отправить
      </button>
    </form>
  );
}
