import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TaskDetailsTab } from './TaskDetailsTab';
import * as tasksApi from '../../api/tasks';
import * as teamsApi from '../../api/teams';
import type { Task, Team } from '../../types';

vi.mock('../../api/tasks', () => ({
  getTasks: vi.fn(),
  getTask: vi.fn(),
  createTask: vi.fn(),
  updateTask: vi.fn().mockResolvedValue({ id: 't-1', product_id: 'p-1', status: 'backlog' }),
  deleteTask: vi.fn(),
  updateTaskStatus: vi.fn().mockResolvedValue({ id: 't-1', product_id: 'p-1', status: 'in_progress' }),
}));

vi.mock('../../api/teams', () => ({
  getTeams: vi.fn(),
  getTeam: vi.fn(),
  createTeam: vi.fn(),
  updateTeam: vi.fn(),
  deleteTeam: vi.fn(),
}));

const teams: Team[] = [
  { id: 'team-1', name: 'Dev Team', description: null, project_scoped: false, created_at: '', updated_at: '', agents_count: 0 },
];

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 't-1',
    title: 'Test Task',
    description: 'Description here',
    product_id: 'p-1',
    team_id: null,
    workflow_id: null,
    status: 'backlog',
    created_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

function renderTab(task: Task = makeTask()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <TaskDetailsTab task={task} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(teamsApi.getTeams).mockResolvedValue(teams);
});

describe('TaskDetailsTab', () => {
  it('renders title and description fields', () => {
    renderTab();
    expect(screen.getByDisplayValue('Test Task')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Description here')).toBeInTheDocument();
  });

  it('saves title on blur', async () => {
    renderTab();
    const input = screen.getByDisplayValue('Test Task');
    fireEvent.change(input, { target: { value: 'Updated Title' } });
    fireEvent.blur(input);
    await waitFor(() => {
      expect(tasksApi.updateTask).toHaveBeenCalledWith('t-1', { title: 'Updated Title' });
    });
  });

  it('does not save title when unchanged', () => {
    renderTab();
    const input = screen.getByDisplayValue('Test Task');
    fireEvent.blur(input);
    expect(tasksApi.updateTask).not.toHaveBeenCalled();
  });

  it('shows "Начать" button for backlog tasks', () => {
    renderTab();
    expect(screen.getByText('Начать')).toBeInTheDocument();
  });

  it('disables "Начать" for invalid tasks (no product_id)', () => {
    renderTab(makeTask({ product_id: null }));
    expect(screen.getByText('Начать')).toBeDisabled();
  });

  it('shows "Завершить" for in_progress tasks', () => {
    renderTab(makeTask({ status: 'in_progress' }));
    expect(screen.getByText('Завершить')).toBeInTheDocument();
  });

  it('shows "Вернуть в работу" for done tasks', () => {
    renderTab(makeTask({ status: 'done' }));
    expect(screen.getByText('Вернуть в работу')).toBeInTheDocument();
  });

  it('shows "Вернуть в работу" for error tasks', () => {
    renderTab(makeTask({ status: 'error' }));
    expect(screen.getByText('Вернуть в работу')).toBeInTheDocument();
  });

  it('shows status badge', () => {
    renderTab(makeTask({ status: 'in_progress' }));
    expect(screen.getByText('In Progress')).toBeInTheDocument();
  });

  it('renders team select with options', async () => {
    renderTab();
    expect(await screen.findByText('Dev Team')).toBeInTheDocument();
  });

  it('saves team change and resets workflow', async () => {
    renderTab();
    await screen.findByText('Dev Team');
    const select = screen.getByRole('combobox', { name: /команда/i });
    fireEvent.change(select, { target: { value: 'team-1' } });
    await waitFor(() => {
      expect(tasksApi.updateTask).toHaveBeenCalledWith('t-1', {
        team_id: 'team-1',
        workflow_id: undefined,
      });
    });
  });
});
