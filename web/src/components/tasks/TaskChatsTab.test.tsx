import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TaskChatsTab } from './TaskChatsTab';
import * as sessionsApi from '../../api/sessions';
import type { Task, SessionListItem } from '../../types';

vi.mock('../../api/sessions', () => ({
  getSessions: vi.fn(),
  getSessionsByTask: vi.fn(),
  getSession: vi.fn(),
  createSession: vi.fn(),
  stopSession: vi.fn(),
}));

vi.mock('../../hooks/useChat', () => ({
  useChat: () => ({
    items: [],
    messages: [],
    status: 'idle' as const,
    error: null,
    pendingApproval: null,
    sendMessage: vi.fn(),
    stopAgent: vi.fn(),
    approveHandoff: vi.fn(),
    rejectHandoff: vi.fn(),
  }),
}));

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 't-1',
    title: 'Test Task',
    description: null,
    product_id: 'p-1',
    team_id: null,
    workflow_id: null,
    status: 'in_progress',
    created_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

function makeSession(overrides: Partial<SessionListItem> = {}): SessionListItem {
  return {
    id: 's-1',
    agent_id: 'a-1',
    agent_name: 'Developer Agent',
    status: 'active',
    created_at: '2024-01-01T00:00:00Z',
    stopped_at: null,
    ...overrides,
  };
}

function renderTab(task: Task = makeTask()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <TaskChatsTab task={task} />
    </QueryClientProvider>,
  );
}

describe('TaskChatsTab', () => {
  it('shows empty message when no sessions', async () => {
    vi.mocked(sessionsApi.getSessionsByTask).mockResolvedValue([]);
    renderTab();
    expect(await screen.findByText('Задача ещё не запущена')).toBeInTheDocument();
  });

  it('renders session sidebar with agent names', async () => {
    vi.mocked(sessionsApi.getSessionsByTask).mockResolvedValue([
      makeSession(),
      makeSession({ id: 's-2', agent_name: 'Reviewer Agent', status: 'stopped' }),
    ]);
    vi.mocked(sessionsApi.getSession).mockResolvedValue({
      id: 's-1',
      agent_id: 'a-1',
      status: 'active',
      claude_session_id: null,
      created_at: '2024-01-01T00:00:00Z',
      stopped_at: null,
      messages: [],
    });
    renderTab();
    expect(await screen.findByText('Developer Agent')).toBeInTheDocument();
    expect(screen.getByText('Reviewer Agent')).toBeInTheDocument();
  });

  it('shows awaiting badge when task is awaiting_user and session is active', async () => {
    vi.mocked(sessionsApi.getSessionsByTask).mockResolvedValue([makeSession()]);
    vi.mocked(sessionsApi.getSession).mockResolvedValue({
      id: 's-1',
      agent_id: 'a-1',
      status: 'active',
      claude_session_id: null,
      created_at: '2024-01-01T00:00:00Z',
      stopped_at: null,
      messages: [],
    });
    renderTab(makeTask({ status: 'awaiting_user' }));
    expect(await screen.findByText('Developer Agent')).toBeInTheDocument();
    expect(screen.getByText('⏳')).toBeInTheDocument();
  });
});
