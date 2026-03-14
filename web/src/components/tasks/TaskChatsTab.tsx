import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTaskSessions } from '../../hooks/useTasks';
import { getSession, stopSession } from '../../api/sessions';
import { useChat } from '../../hooks/chat/useChat';
import { ChatWindow } from '../ChatWindow';
import type { Task, Session, SessionListItem } from '../../types';
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

  // Auto-select active session (or last one)
  useEffect(() => {
    if (sessions?.length && !selectedId) {
      const active = sessions.find((s) => s.status === 'active');
      setSelectedId((active || sessions[sessions.length - 1])!.id);
    }
  }, [sessions, selectedId]);

  // Auto-switch to new session when it appears (peer handoff created it)
  useEffect(() => {
    if (!sessions?.length) return;
    const currentIds = new Set(sessions.map((s) => s.id));
    const prevIds = prevSessionIdsRef.current;

    if (prevIds.size > 0) {
      for (const id of currentIds) {
        if (!prevIds.has(id)) {
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

  const activeId = selectedId ?? sessions[sessions.length - 1]!.id;

  return (
    <div className="flex flex-1 min-h-0">
      <SessionSidebar
        sessions={sessions}
        activeId={activeId}
        taskStatus={task.status}
        onSelect={setSelectedId}
      />
      <div className="flex flex-1 flex-col min-w-0">
        <ActiveSessionChat
          key={activeId}
          sessionId={activeId}
          task={task}
          queryClient={queryClient}
        />
      </div>
    </div>
  );
}

// ── Active session chat — own WS per session ─────────────────────────────

function ActiveSessionChat({
  sessionId,
  task,
  queryClient,
}: {
  sessionId: string;
  task: Task;
  queryClient: ReturnType<typeof useQueryClient>;
}) {
  const [approvedLocally, setApprovedLocally] = useState(false);
  const { data: session } = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => getSession(sessionId),
    enabled: Boolean(sessionId),
  });

  const isActive = session?.status === 'active';
  const mainLoaded = Boolean(session);

  // Each session gets its own useChat with its own WebSocket
  const chat = useChat(
    sessionId,
    session?.messages ?? [],
    mainLoaded && isActive,
  );

  // Reset approvedLocally when a new approval_required arrives
  useEffect(() => {
    if (chat.status === 'awaiting_approval') {
      setApprovedLocally(false);
    }
  }, [chat.status]);

  async function handleStop() {
    chat.stopAgent();
    await stopSession(sessionId);
    void queryClient.invalidateQueries({ queryKey: ['sessions'] });
    void queryClient.invalidateQueries({ queryKey: ['sessions', 'by-task', task.id] });
  }

  function handleApprove() {
    chat.approveHandoff();
    setApprovedLocally(true);
    void queryClient.invalidateQueries({ queryKey: ['tasks', 'detail', task.id] });
    void queryClient.invalidateQueries({ queryKey: ['sessions', 'by-task', task.id] });
  }

  function handleRefine(comment: string) {
    chat.refineHandoff(comment);
    void queryClient.invalidateQueries({ queryKey: ['tasks', 'detail', task.id] });
  }

  const wsReady = chat.status === 'connected' || chat.status === 'awaiting_approval' || chat.status === 'typing';
  const showApproval =
    (task.status === 'awaiting_user' || chat.status === 'awaiting_approval')
    && isActive && wsReady && !approvedLocally;

  const canSend = chat.status === 'connected' && isActive && !showApproval;

  return (
    <>
      <div className="flex items-center justify-between border-b px-4 py-2 bg-white">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">{sessionId.slice(0, 8)}...</span>
          {isActive && (chat.status === 'typing' || chat.status === 'tool') && (
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
              <span className="text-xs text-gray-500">Работает...</span>
            </span>
          )}
        </div>
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

      {showApproval && (
        <ApprovalCard
          approval={chat.pendingApproval || { fromAgent: 'Агент', toAgent: '...', task: 'Ожидает вашего решения' }}
          onApprove={handleApprove}
          onRefine={handleRefine}
        />
      )}

      {canSend && (
        <ChatInput onSend={chat.sendMessage} disabled={!canSend} />
      )}
    </>
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
