import { useState } from 'react';
import { useTask } from '../../hooks/useTasks';
import { TaskDetailsTab } from './TaskDetailsTab';
import { TaskChatsTab } from './TaskChatsTab';

type TabId = 'details' | 'chats';

interface TaskViewProps {
  taskId: string;
  onClose?: () => void;
  initialTab?: TabId;
}

export function TaskView({ taskId, onClose, initialTab = 'details' }: TaskViewProps) {
  const [activeTab, setActiveTab] = useState<TabId>(initialTab);
  const { data: task, isLoading } = useTask(taskId);

  if (isLoading || !task) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-gray-400 text-sm">Загрузка задачи...</p>
      </div>
    );
  }

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <h2 className="text-lg font-semibold text-gray-900 truncate pr-4">
          {task.title}
        </h2>
        {onClose && (
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none"
            aria-label="Закрыть"
          >
            &times;
          </button>
        )}
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
        {activeTab === 'details' && <TaskDetailsTab task={task} onDelete={onClose} onStarted={() => setActiveTab('chats')} />}
        {activeTab === 'chats' && <TaskChatsTab task={task} />}
      </div>
    </>
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
