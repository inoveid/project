import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTaskSessions } from '../../hooks/useTasks';
import { getSession, stopSession } from '../../api/sessions';
import { useChat } from '../../hooks/useChat';
import { ChatWindow } from '../ChatWindow';
import type { Task, SessionListItem } from '../../types';
import { isHandoffItem } from '../../types';
import { ApprovalCard } from '../ApprovalCard';

interface TaskChatsTabProps {
  task: Task;
}

export function TaskChatsTab({ task }: TaskChatsTabProps) {
  const { data: sessions, isLoading } = useTaskSessions(task.id, task.status);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const prevSessionIdsRef = useRef<Set<string>>(new Set());

  // Auto-switch to active session when task awaits approval
  useEffect(() => {
    if (task.status === 'awaiting_user' && sessions?.length) {
      const activeSession = sessions.find((s) => s.status === 'active');
      if (activeSession && activeSession.id !== selectedId) {
        setSelectedId(activeSession.id);
      }
    }
  }, [task.status, sessions, selectedId]);

  // Auto-switch to new session when it appears (after approve/handoff)
  useEffect(() => {
    if (!sessions?.length) return;
    const currentIds = new Set(sessions.map((s) => s.id));
    const prevIds = prevSessionIdsRef.current;

    if (prevIds.size > 0) {
      for (const id of currentIds) {
        if (!prevIds.has(id)) {
          // New session appeared — switch to it
          setSelectedId(id);
          break;
        }
      }
    }
    prevSessionIdsRef.current = currentIds;
  }, [sessions]);

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

  // Sessions sorted by created_at DESC — main session is the oldest (last)
  const mainSessionId = sessions[sessions.length - 1]?.id ?? '';
  const activeId = selectedId ?? mainSessionId;
  const isMainSession = activeId === mainSessionId;

  return (
    <div className="flex flex-1 min-h-0">
      <SessionSidebar
        sessions={sessions}
        activeId={activeId}
        taskStatus={task.status}
        onSelect={setSelectedId}
      />
      <SessionChat
        key={activeId}
        sessionId={activeId}
        task={task}
        enableWs={isMainSession}
      />
    </div>
  );
}

// ── Session sidebar ──────────────────────────────────────────────────────────

function SessionSidebar({
  sessions,
  activeId,
  taskStatus,
  onSelect,
}: {
  sessions: SessionListItem[];
  activeId: string;
  taskStatus: Task['status'];
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
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ── Session chat area ────────────────────────────────────────────────────────

function SessionChat({
  sessionId,
  task,
  enableWs,
}: {
  sessionId: string;
  task: Task;
  enableWs: boolean;
}) {
  const queryClient = useQueryClient();

  const {
    data: session,
    isLoading,
    error: loadError,
  } = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => getSession(sessionId),
    enabled: Boolean(sessionId),
    // Sub-sessions: poll DB for messages since no WS events
    refetchInterval: !enableWs && task.status === 'in_progress' ? 2000 : false,
  });

  const sessionLoaded = Boolean(session);
  const isActiveSession = session?.status === 'active';

  const {
    items,
    status,
    error: chatError,
    pendingApproval,
    sendMessage,
    stopAgent,
    approveHandoff,
    rejectHandoff,
  } = useChat(sessionId, session?.messages ?? [], sessionLoaded && isActiveSession && enableWs);

  async function handleStop() {
    stopAgent();
    await stopSession(sessionId);
    void queryClient.invalidateQueries({ queryKey: ['sessions'] });
    void queryClient.invalidateQueries({ queryKey: ['sessions', 'by-task', task.id] });
  }

  function handleApprove() {
    approveHandoff();
    void queryClient.invalidateQueries({ queryKey: ['tasks', 'detail', task.id] });
  }

  function handleReject() {
    rejectHandoff();
    void queryClient.invalidateQueries({ queryKey: ['tasks', 'detail', task.id] });
  }

  if (isLoading) {
    return <p className="text-gray-400 text-sm p-4 flex-1">Загрузка чата...</p>;
  }

  if (loadError) {
    return (
      <p className="text-red-600 text-sm p-4 flex-1">
        Ошибка загрузки: {loadError.message}
      </p>
    );
  }

  // Derive approval from multiple sources for reliability
  const approvalFromItems = (() => {
    const last = items.filter((i) => isHandoffItem(i) && i.itemType === 'approval_required').pop();
    if (last && isHandoffItem(last) && last.fromAgent && last.toAgent) {
      return { fromAgent: last.fromAgent, toAgent: last.toAgent, task: last.content };
    }
    return null;
  })();
  const effectiveApproval = pendingApproval || approvalFromItems;
  const showApproval = task.status === 'awaiting_user' && isActiveSession && enableWs;
  const canSend = status === 'connected' && isActiveSession && enableWs && !showApproval;

  // For sub-sessions or stopped sessions: show DB messages
  const displayItems = (enableWs && isActiveSession) ? items : (session?.messages ?? []);

  return (
    <div className="flex flex-1 flex-col min-w-0">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-2 bg-white">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">{sessionId.slice(0, 8)}...</span>
          {!enableWs && isActiveSession && task.status === 'in_progress' && (
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
              <span className="text-xs text-gray-500">Работает...</span>
            </span>
          )}
        </div>
        {isActiveSession && enableWs && (
          <button
            onClick={() => void handleStop()}
            disabled={status === 'disconnected' || status === 'idle'}
            className="rounded border border-red-300 px-3 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-50"
          >
            Stop
          </button>
        )}
      </div>

      {chatError && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-2 text-sm text-red-600">
          {chatError}
        </div>
      )}

      {/* Messages */}
      <ChatWindow items={displayItems} />

      {/* Input / Approval */}
      {showApproval ? (
        <ApprovalCard
          approval={effectiveApproval || { fromAgent: 'Агент', toAgent: '...', task: 'Ожидает вашего решения' }}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      ) : canSend ? (
        <ChatInput onSend={sendMessage} disabled={!canSend} />
      ) : null}
    </div>
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
