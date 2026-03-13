import { useDraggable } from '@dnd-kit/core';
import type { Task } from '../../types';
import { getStatusConfig, isTaskValid } from './statusConfig';

interface TaskCardProps {
  task: Task;
  onClick: () => void;
  onStart?: (taskId: string) => void;
  onDelete?: (taskId: string) => void;
}

export function TaskCard({ task, onClick, onStart, onDelete }: TaskCardProps) {
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
      <div className="flex items-start justify-between">
        <button
          type="button"
          onClick={onClick}
          className="flex-1 text-left"
        >
        <p className="font-semibold text-sm text-gray-900 mb-1">{task.title}</p>
        <span
          className={`inline-block text-xs px-2 py-0.5 rounded-full ${statusCfg.colorClasses}`}
        >
          {statusCfg.label}
        </span>
        {task.status === 'error' && task.error_message && (
          <p className="text-[11px] text-red-600 mt-1 line-clamp-2">{task.error_message}</p>
        )}
        </button>
        {onDelete && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(task.id);
            }}
            className="ml-1 p-1 text-gray-300 hover:text-red-500 rounded transition-colors"
            title="Удалить задачу"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        )}
      </div>

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
