import { useDraggable } from '@dnd-kit/core';
import type { Task } from '../../types';
import { getStatusConfig, isTaskValid } from './statusConfig';

interface TaskCardProps {
  task: Task;
  onClick: () => void;
  onStart?: (taskId: string) => void;
}

export function TaskCard({ task, onClick, onStart }: TaskCardProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: task.id,
    data: { task },
  });

  const statusCfg = getStatusConfig(task.status);
  const canStart = task.status === 'backlog' && isTaskValid(task);

  const style = transform
    ? { transform: `translate(${transform.x}px, ${transform.y}px)` }
    : undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className={`rounded border border-gray-200 bg-white p-3 shadow-sm cursor-grab ${
        isDragging ? 'opacity-50 shadow-lg' : ''
      }`}
    >
      <button
        type="button"
        onClick={onClick}
        className="w-full text-left"
      >
        <p className="font-semibold text-sm text-gray-900 mb-1">{task.title}</p>
        <span
          className={`inline-block text-xs px-2 py-0.5 rounded-full ${statusCfg.colorClasses}`}
        >
          {statusCfg.label}
        </span>
      </button>

      {canStart && onStart && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onStart(task.id);
          }}
          className="mt-2 w-full text-center text-xs bg-blue-600 text-white rounded px-2 py-1 hover:bg-blue-700"
        >
          Начать
        </button>
      )}
    </div>
  );
}
