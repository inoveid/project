import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DndContext } from '@dnd-kit/core';
import { KanbanColumn } from './KanbanColumn';
import type { Task } from '../../types';

function makeTask(id: string, title: string): Task {
  return {
    id,
    title,
    description: null,
    product_id: 'p-1',
    team_id: null,
    workflow_id: null,
    status: 'backlog',
    created_at: '2024-01-01T00:00:00Z',
  };
}

function renderWithDnd(ui: React.ReactElement) {
  return render(<DndContext>{ui}</DndContext>);
}

describe('KanbanColumn', () => {
  it('renders title and task count', () => {
    const tasks = [makeTask('1', 'Task A'), makeTask('2', 'Task B')];
    renderWithDnd(
      <KanbanColumn
        title="Backlog"
        status="backlog"
        tasks={tasks}
        onTaskClick={vi.fn()}
      />,
    );
    const heading = screen.getByRole('heading', { level: 3 });
    expect(heading).toHaveTextContent('Backlog');
    expect(heading).toHaveTextContent('(2)');
  });

  it('renders task cards', () => {
    const tasks = [makeTask('1', 'Task A')];
    renderWithDnd(
      <KanbanColumn
        title="Backlog"
        status="backlog"
        tasks={tasks}
        onTaskClick={vi.fn()}
      />,
    );
    expect(screen.getByText('Task A')).toBeInTheDocument();
  });

  it('shows empty message when no tasks', () => {
    renderWithDnd(
      <KanbanColumn
        title="Backlog"
        status="backlog"
        tasks={[]}
        onTaskClick={vi.fn()}
      />,
    );
    expect(screen.getByText('Нет задач')).toBeInTheDocument();
  });

  it('shows "Показать ещё" when tasks exceed page size', () => {
    const tasks = Array.from({ length: 25 }, (_, i) => makeTask(`t-${i}`, `Task ${i}`));
    renderWithDnd(
      <KanbanColumn
        title="Backlog"
        status="backlog"
        tasks={tasks}
        onTaskClick={vi.fn()}
      />,
    );
    const btn = screen.getByText(/Показать ещё/);
    expect(btn).toBeInTheDocument();
    expect(btn.textContent).toContain('5');
  });

  it('loads more tasks when "Показать ещё" clicked', () => {
    const tasks = Array.from({ length: 25 }, (_, i) => makeTask(`t-${i}`, `Task ${i}`));
    renderWithDnd(
      <KanbanColumn
        title="Backlog"
        status="backlog"
        tasks={tasks}
        onTaskClick={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByText(/Показать ещё/));
    expect(screen.queryByText(/Показать ещё/)).not.toBeInTheDocument();
    expect(screen.getByText('Task 24')).toBeInTheDocument();
  });

  it('shows add button when showAddButton is true', () => {
    const onAddClick = vi.fn();
    renderWithDnd(
      <KanbanColumn
        title="Backlog"
        status="backlog"
        tasks={[]}
        onTaskClick={vi.fn()}
        showAddButton
        onAddClick={onAddClick}
      />,
    );
    fireEvent.click(screen.getByTitle('Создать задачу'));
    expect(onAddClick).toHaveBeenCalled();
  });
});
