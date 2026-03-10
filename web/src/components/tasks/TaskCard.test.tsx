import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DndContext } from '@dnd-kit/core';
import { TaskCard } from './TaskCard';
import type { Task } from '../../types';

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 't-1',
    title: 'Test Task',
    description: null,
    product_id: 'p-1',
    team_id: null,
    workflow_id: null,
    status: 'backlog',
    created_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

function renderWithDnd(ui: React.ReactElement) {
  return render(<DndContext>{ui}</DndContext>);
}

describe('TaskCard', () => {
  it('renders task title and status badge', () => {
    renderWithDnd(<TaskCard task={makeTask()} onClick={vi.fn()} />);
    expect(screen.getByText('Test Task')).toBeInTheDocument();
    expect(screen.getByText('Backlog')).toBeInTheDocument();
  });

  it('shows "Начать" button for valid backlog tasks', () => {
    const onStart = vi.fn();
    renderWithDnd(<TaskCard task={makeTask()} onClick={vi.fn()} onStart={onStart} />);
    const btn = screen.getByText('Начать');
    fireEvent.click(btn);
    expect(onStart).toHaveBeenCalledWith('t-1');
  });

  it('does not show "Начать" for tasks without product_id', () => {
    renderWithDnd(
      <TaskCard task={makeTask({ product_id: null })} onClick={vi.fn()} onStart={vi.fn()} />,
    );
    expect(screen.queryByText('Начать')).not.toBeInTheDocument();
  });

  it('does not show "Начать" for non-backlog tasks', () => {
    renderWithDnd(
      <TaskCard task={makeTask({ status: 'in_progress' })} onClick={vi.fn()} onStart={vi.fn()} />,
    );
    expect(screen.queryByText('Начать')).not.toBeInTheDocument();
  });

  it('shows awaiting_user badge', () => {
    renderWithDnd(
      <TaskCard task={makeTask({ status: 'awaiting_user' })} onClick={vi.fn()} />,
    );
    expect(screen.getByText('⏳ Ждёт решения')).toBeInTheDocument();
  });

  it('calls onClick when card is clicked', () => {
    const onClick = vi.fn();
    renderWithDnd(<TaskCard task={makeTask()} onClick={onClick} />);
    fireEvent.click(screen.getByText('Test Task'));
    expect(onClick).toHaveBeenCalled();
  });
});
