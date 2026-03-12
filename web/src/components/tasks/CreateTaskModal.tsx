import { useEffect, useState } from 'react';
import { getWorkflows } from '../../api/workflows';
import type { Workflow } from '../../types';

interface CreateTaskModalProps {
  productId: string;
  teams: Array<{ id: string; name: string }>;
  defaultTeamId?: string | null;
  onSubmit: (data: { title: string; description?: string; product_id: string; team_id?: string; workflow_id?: string }) => void;
  onClose: () => void;
  isLoading: boolean;
}

export function CreateTaskModal({ productId, teams, defaultTeamId, onSubmit, onClose, isLoading }: CreateTaskModalProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [teamId, setTeamId] = useState(defaultTeamId ?? '');
  const [workflowId, setWorkflowId] = useState('');
  const [workflows, setWorkflows] = useState<Workflow[]>([]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && !isLoading) onClose();
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose, isLoading]);

  useEffect(() => {
    if (!teamId) {
      setWorkflows([]);
      setWorkflowId('');
      return;
    }
    getWorkflows(teamId).then((wfs) => {
      setWorkflows(wfs);
      setWorkflowId(wfs.length === 1 ? wfs[0].id : '');
    });
  }, [teamId]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) return;
    const payload: { title: string; description?: string; product_id: string; team_id?: string; workflow_id?: string } = {
      title: trimmed,
      product_id: productId,
    };
    const descTrimmed = description.trim();
    if (descTrimmed) payload.description = descTrimmed;
    if (teamId) payload.team_id = teamId;
    if (workflowId) payload.workflow_id = workflowId;
    onSubmit(payload);
  }

  function handleBackdropClick(e: React.MouseEvent) {
    if (e.target === e.currentTarget && !isLoading) onClose();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={handleBackdropClick}
      role="presentation"
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <h2 className="text-lg font-semibold mb-4">Новая задача</h2>
        <form onSubmit={handleSubmit}>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Название
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Введите название задачи"
            autoFocus
            required
          />

          <label className="block text-sm font-medium text-gray-700 mb-1 mt-3">
            Описание
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            placeholder="Опишите задачу для агента (необязательно)"
            rows={3}
          />

          <label className="block text-sm font-medium text-gray-700 mb-1 mt-3">
            Команда
          </label>
          <select
            value={teamId}
            onChange={(e) => setTeamId(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Без команды</option>
            {teams.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>

          {workflows.length > 0 && (
            <>
              <label className="block text-sm font-medium text-gray-700 mb-1 mt-3">
                Workflow
              </label>
              <select
                value={workflowId}
                onChange={(e) => setWorkflowId(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Без workflow</option>
                {workflows.map((w) => (
                  <option key={w.id} value={w.id}>{w.name}</option>
                ))}
              </select>
            </>
          )}

          <div className="flex justify-end gap-2 mt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
              disabled={isLoading}
            >
              Отмена
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
              disabled={isLoading || !title.trim()}
            >
              {isLoading ? 'Создание...' : 'Создать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
