import { useEffect } from 'react';
import { TaskView } from './TaskView';

interface TaskModalProps {
  taskId: string;
  onClose: () => void;
}

export function TaskModal({ taskId, onClose }: TaskModalProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl flex flex-col"
        style={{ width: 900, maxWidth: '95vw', height: '80vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        <TaskView taskId={taskId} onClose={onClose} />
      </div>
    </div>
  );
}
