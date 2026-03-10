import type { TaskStatus } from '../../types';

interface StatusConfig {
  label: string;
  colorClasses: string;
  icon?: string;
}

const STATUS_MAP: Record<TaskStatus, StatusConfig> = {
  backlog: { label: 'Backlog', colorClasses: 'bg-gray-100 text-gray-700' },
  in_progress: { label: 'In Progress', colorClasses: 'bg-blue-100 text-blue-700' },
  awaiting_user: { label: '⏳ Ждёт решения', colorClasses: 'bg-yellow-100 text-yellow-700', icon: '⏳' },
  done: { label: 'Готово', colorClasses: 'bg-green-100 text-green-700' },
  error: { label: 'Ошибка', colorClasses: 'bg-red-100 text-red-700' },
};

export function getStatusConfig(status: TaskStatus): StatusConfig {
  return STATUS_MAP[status];
}

/** Task is valid when it has product_id assigned */
export function isTaskValid(task: { product_id: string | null }): boolean {
  return task.product_id !== null;
}

/**
 * Drag-only transitions (subset of backend VALID_TRANSITIONS).
 * awaiting_user and error statuses are set by the system, not by user drag.
 * Backend also allows: in_progress → awaiting_user, in_progress → error.
 */
const ALLOWED_TRANSITIONS: Partial<Record<TaskStatus, TaskStatus[]>> = {
  backlog: ['in_progress'],
  in_progress: ['done'],
  done: ['in_progress'],
  error: ['in_progress'],
};

export function isTransitionAllowed(from: TaskStatus, to: TaskStatus): boolean {
  return ALLOWED_TRANSITIONS[from]?.includes(to) ?? false;
}

export function getTransitionError(from: TaskStatus, to: TaskStatus): string | null {
  if (isTransitionAllowed(from, to)) return null;
  return `Нельзя перенести задачу из «${STATUS_MAP[from].label}» в «${STATUS_MAP[to].label}»`;
}
