import { useState } from 'react';
import { useTask } from '../../hooks/useTasks';
import { TaskDetailsTab } from './TaskDetailsTab';
import { TaskChatsTab } from './TaskChatsTab';

type TabId = 'details' | 'chats';

interface TaskModalProps {
  taskId: string;
  onClose: () => void;
}

export function TaskModal({ taskId, onClose }: TaskModalProps) {
  const [activeTab, setActiveTab] = useState<TabId>('details');
  const { data: task, isLoading } = useTask(taskId);

  if (isLoading || !task) {
    return (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
        onClick={onClose}
      >
        <div className="bg-white rounded-lg shadow-xl px-8 py-6">
          <p className="text-gray-400 text-sm">Загрузка задачи...</p>
        </div>
      </div>
    );
  }

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
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900 truncate pr-4">
            {task.title}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none"
            aria-label="Закрыть"
          >
            &times;
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b px-6">
          <TabButton
            label="Детали"
            active={activeTab === 'details'}
            onClick={() => setActiveTab('details')}
          />
          <TabButton
            label="Чаты"
            active={activeTab === 'chats'}
            onClick={() => setActiveTab('chats')}
          />
        </div>

        {/* Content */}
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          {activeTab === 'details' && <TaskDetailsTab task={task} onDelete={onClose} />}
          {activeTab === 'chats' && <TaskChatsTab task={task} />}
        </div>
      </div>
    </div>
  );
}

function TabButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px ${
        active
          ? 'border-blue-600 text-blue-600'
          : 'border-transparent text-gray-500 hover:text-gray-700'
      }`}
    >
      {label}
    </button>
  );
}
