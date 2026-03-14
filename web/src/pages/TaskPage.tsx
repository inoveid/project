import { useParams, useNavigate } from 'react-router-dom';
import { TaskView } from '../components/tasks/TaskView';

export function TaskPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  if (!id) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <p className="text-gray-400">Задача не найдена</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="bg-white rounded-lg shadow-sm border flex flex-col" style={{ minHeight: '70vh' }}>
        <TaskView taskId={id} onClose={() => navigate(-1)} />
      </div>
    </div>
  );
}
