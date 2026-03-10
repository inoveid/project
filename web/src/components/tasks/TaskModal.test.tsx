import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TaskModal } from './TaskModal';
import * as tasksApi from '../../api/tasks';
import type { Task } from '../../types';

vi.mock('../../api/teams', () => ({
  getTeams: vi.fn().mockResolvedValue([]),
  getTeam: vi.fn(),
  createTeam: vi.fn(),
  updateTeam: vi.fn(),
  deleteTeam: vi.fn(),
}));

vi.mock('../../api/tasks', () => ({
  getTasks: vi.fn(),
  getTask: vi.fn(),
  createTask: vi.fn(),
  updateTask: vi.fn(),
  deleteTask: vi.fn(),
  updateTaskStatus: vi.fn(),
}));

vi.mock('../../api/sessions', () => ({
  getSessions: vi.fn(),
  getSessionsByTask: vi.fn().mockResolvedValue([]),
  getSession: vi.fn(),
  createSession: vi.fn(),
  stopSession: vi.fn(),
}));

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 't-1',
    title: 'Test Task',
    description: 'A test description',
    product_id: 'p-1',
    team_id: null,
    workflow_id: null,
    status: 'backlog',
    created_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

function renderModal(taskId = 't-1', onClose = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <TaskModal taskId={taskId} onClose={onClose} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(tasksApi.getTask).mockResolvedValue(makeTask());
});

describe('TaskModal', () => {
  it('renders task title in header', async () => {
    renderModal();
    expect(await screen.findByText('Test Task')).toBeInTheDocument();
  });

  it('renders both tabs', async () => {
    renderModal();
    expect(await screen.findByText('Детали')).toBeInTheDocument();
    expect(screen.getByText('Чаты')).toBeInTheDocument();
  });

  it('defaults to Details tab', async () => {
    renderModal();
    expect(await screen.findByText('Название')).toBeInTheDocument();
    expect(screen.getByText('Описание')).toBeInTheDocument();
  });

  it('switches to Chats tab', async () => {
    renderModal();
    await screen.findByText('Чаты');
    fireEvent.click(screen.getByText('Чаты'));
    expect(await screen.findByText('Задача ещё не запущена')).toBeInTheDocument();
  });

  it('shows loading state initially', () => {
    vi.mocked(tasksApi.getTask).mockReturnValue(new Promise(() => undefined));
    renderModal();
    expect(screen.getByText('Загрузка задачи...')).toBeInTheDocument();
  });

  it('calls onClose when close button clicked', async () => {
    const onClose = vi.fn();
    renderModal('t-1', onClose);
    await screen.findByLabelText('Закрыть');
    fireEvent.click(screen.getByLabelText('Закрыть'));
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when backdrop clicked', async () => {
    const onClose = vi.fn();
    const { container } = renderModal('t-1', onClose);
    await screen.findByText('Test Task');
    const backdrop = container.querySelector('.fixed.inset-0');
    if (backdrop) fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalled();
  });
});
