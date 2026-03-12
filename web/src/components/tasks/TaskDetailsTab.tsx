import { useCallback, useEffect, useRef, useState } from 'react';
import { useTeams } from '../../hooks/useTeams';
import { getWorkflows } from '../../api/workflows';
import type { Workflow } from '../../types';
import { useUpdateTask, useUpdateTaskStatus } from '../../hooks/useTasks';
import { getStatusConfig, isTaskValid } from './statusConfig';
import type { Task, TaskUpdate } from '../../types';

interface TaskDetailsTabProps {
  task: Task;
}

const REQUIRED_FIELDS: ReadonlyArray<keyof Task> = ['description', 'team_id', 'workflow_id'];

function getMissingFields(task: Task): Set<string> {
  const missing = new Set<string>();
  for (const f of REQUIRED_FIELDS) {
    if (!task[f]) missing.add(f);
  }
  return missing;
}

export function TaskDetailsTab({ task }: TaskDetailsTabProps) {
  const { data: teams } = useTeams();
  const updateTask = useUpdateTask();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);

  useEffect(() => {
    if (!task.team_id) {
      setWorkflows([]);
      return;
    }
    getWorkflows(task.team_id).then(setWorkflows);
  }, [task.team_id]);
  const updateStatus = useUpdateTaskStatus();

  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description ?? '');
  const [showValidation, setShowValidation] = useState(false);
  const prevTaskIdRef = useRef(task.id);

  useEffect(() => {
    if (prevTaskIdRef.current !== task.id) {
      prevTaskIdRef.current = task.id;
      setTitle(task.title);
      setDescription(task.description ?? '');
      setShowValidation(false);
    }
  }, [task.id, task.title, task.description]);

  const missingFields = showValidation ? getMissingFields(task) : new Set<string>();

  const saveField = useCallback(
    (data: TaskUpdate) => {
      updateTask.mutate({ id: task.id, data });
    },
    [task.id, updateTask],
  );

  function handleTitleBlur() {
    const trimmed = title.trim();
    if (trimmed && trimmed !== task.title) {
      saveField({ title: trimmed });
    }
  }

  function handleTitleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.currentTarget.blur();
    }
  }

  function handleDescriptionBlur() {
    if (description !== (task.description ?? '')) {
      saveField({ description });
    }
  }

  function handleTeamChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const teamId = e.target.value || undefined;
    saveField({ team_id: teamId, workflow_id: undefined });
  }

  const statusCfg = getStatusConfig(task.status);
  const valid = isTaskValid(task);

  return (
    <div className="space-y-5 p-6 overflow-y-auto">
      {/* Title */}
      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">Название</label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={handleTitleBlur}
          onKeyDown={handleTitleKeyDown}
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        />
      </div>

      {/* Description */}
      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">Описание</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          onBlur={handleDescriptionBlur}
          rows={4}
          className={`w-full rounded border px-3 py-2 text-sm focus:outline-none resize-y ${missingFields.has('description') ? 'border-red-400 focus:border-red-500' : 'border-gray-300 focus:border-blue-500'}`}
        />
      </div>

      {/* Team */}
      <div>
        <label htmlFor="task-team-select" className="block text-xs font-medium text-gray-500 mb-1">Команда</label>
        <select
          id="task-team-select"
          value={task.team_id ?? ''}
          onChange={handleTeamChange}
          className={`w-full rounded border px-3 py-2 text-sm focus:outline-none ${missingFields.has('team_id') ? 'border-red-400 focus:border-red-500' : 'border-gray-300 focus:border-blue-500'}`}
        >
          <option value="">— не выбрана —</option>
          {teams?.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </div>

      {/* Workflow */}
      <div>
        <label htmlFor="task-workflow-select" className="block text-xs font-medium text-gray-500 mb-1">Workflow</label>
        <select
          id="task-workflow-select"
          value={task.workflow_id ?? ''}
          onChange={(e) => saveField({ workflow_id: e.target.value || undefined })}
          disabled={!task.team_id || workflows.length === 0}
          className={`w-full rounded border px-3 py-2 text-sm focus:outline-none disabled:bg-gray-50 disabled:text-gray-400 ${missingFields.has('workflow_id') ? 'border-red-400 focus:border-red-500' : 'border-gray-300 focus:border-blue-500'}`}
        >
          <option value="">— не выбран —</option>
          {workflows.map((w) => (
            <option key={w.id} value={w.id}>{w.name}</option>
          ))}
        </select>
      </div>

      {/* Status badge */}
      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">Статус</label>
        <span className={`inline-block text-xs px-2 py-0.5 rounded-full ${statusCfg.colorClasses}`}>
          {statusCfg.label}
        </span>
      </div>

      {/* Action buttons */}
      <div className="pt-2">
        <StatusActions
          task={task}
          valid={valid}
          onChangeStatus={(status) => updateStatus.mutate({ id: task.id, status })}
          isPending={updateStatus.isPending}
          onValidationFail={() => setShowValidation(true)}
          showValidation={showValidation}
        />
      </div>
    </div>
  );
}

// ── Status action buttons ───────────────────────────────────────────────────

function StatusActions({
  task,
  valid,
  onChangeStatus,
  isPending,
  onValidationFail,
  showValidation,
}: {
  task: Task;
  valid: boolean;
  onChangeStatus: (status: Task['status']) => void;
  isPending: boolean;
  onValidationFail: () => void;
  showValidation: boolean;
}) {
  if (task.status === 'backlog') {
    const missing = getMissingFields(task);
    const canStart = valid && missing.size === 0;
    return (
      <div>
        {showValidation && !canStart && (
          <p className="text-sm text-red-500 mb-2">Заполните обязательные поля в задаче</p>
        )}
        <button
          type="button"
          disabled={isPending}
          onClick={() => {
            if (!canStart) {
              onValidationFail();
              return;
            }
            onChangeStatus('in_progress');
          }}
          className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Начать
        </button>
      </div>
    );
  }

  if (task.status === 'in_progress') {
    return (
      <button
        type="button"
        disabled={isPending}
        onClick={() => onChangeStatus('done')}
        className="rounded bg-green-600 px-4 py-2 text-sm text-white hover:bg-green-700 disabled:opacity-50"
      >
        Завершить
      </button>
    );
  }

  if (task.status === 'done' || task.status === 'error') {
    return (
      <button
        type="button"
        disabled={isPending}
        onClick={() => onChangeStatus('in_progress')}
        className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
      >
        Вернуть в работу
      </button>
    );
  }

  return null;
}
