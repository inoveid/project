import { useEffect, useState } from 'react';
import { useDroppable } from '@dnd-kit/core';
import type { Task, TaskStatus } from '../../types';
import { TaskCard } from './TaskCard';

const PAGE_SIZE = 20;

interface KanbanColumnProps {
  title: string;
  status: TaskStatus;
  tasks: Task[];
  onTaskClick: (task: Task) => void;
  onStartTask?: (taskId: string) => void;
  onDeleteTask?: (taskId: string) => void;
  showAddButton?: boolean;
  onAddClick?: () => void;
}

export function KanbanColumn({
  title,
  status,
  tasks,
  onTaskClick,
  onStartTask,
  onDeleteTask,
  showAddButton,
  onAddClick,
}: KanbanColumnProps) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  // Reset pagination when the task list identity changes (e.g. filter switch)
  useEffect(() => { setVisibleCount(PAGE_SIZE); }, [tasks]);

  const { isOver, setNodeRef } = useDroppable({
    id: status,
    data: { status },
  });

  const visibleTasks = tasks.slice(0, visibleCount);
  const hasMore = tasks.length > visibleCount;

  return (
    <div
      ref={setNodeRef}
      className={`flex flex-col min-w-[260px] w-[280px] rounded-lg border bg-gray-50 ${
        isOver ? 'border-blue-400 bg-blue-50' : 'border-gray-200'
      }`}
    >
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200">
        <h3 className="text-sm font-semibold text-gray-700">
          {title}{' '}
          <span className="text-gray-400 font-normal">({tasks.length})</span>
        </h3>
        {showAddButton && (
          <button
            type="button"
            onClick={onAddClick}
            className="text-blue-600 hover:text-blue-800 text-lg leading-none"
            title="Создать задачу"
          >
            +
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-2 max-h-[calc(100vh-260px)]">
        {visibleTasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            onClick={() => onTaskClick(task)}
            onStart={status === 'backlog' ? onStartTask : undefined}
            onDelete={onDeleteTask}
          />
        ))}

        {tasks.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-4">Нет задач</p>
        )}

        {hasMore && (
          <button
            type="button"
            onClick={() => setVisibleCount((prev) => prev + PAGE_SIZE)}
            className="w-full text-xs text-blue-600 hover:text-blue-800 py-1"
          >
            Показать ещё ({tasks.length - visibleCount})
          </button>
        )}
      </div>
    </div>
  );
}
