import { useCallback, useEffect, useMemo, useState } from 'react';
import { DndContext, DragEndEvent, DragOverlay, DragStartEvent, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { useBusinesses } from '../hooks/useBusinesses';
import { useProducts } from '../hooks/useProducts';
import { useTeams } from '../hooks/useTeams';
import { useTasks, useCreateTask, useUpdateTaskStatus } from '../hooks/useTasks';
import { KanbanColumn } from '../components/tasks/KanbanColumn';
import { TaskCard } from '../components/tasks/TaskCard';
import { CreateTaskModal } from '../components/tasks/CreateTaskModal';
import { FilterBar } from '../components/tasks/FilterBar';
import { TaskModal } from '../components/tasks/TaskModal';
import { useToast } from '../hooks/useToast';
import { isTransitionAllowed, getTransitionError } from '../components/tasks/statusConfig';
import type { Task, TaskStatus } from '../types';
import { isTask, isTaskStatus } from '../types';

const STORAGE_KEY = 'dashboard_filters';

interface DashboardFilters {
  businessId: string | null;
  productId: string | null;
  teamId: string | null;
}

const EMPTY_FILTERS: DashboardFilters = { businessId: null, productId: null, teamId: null };

function isNullOrString(v: unknown): v is string | null {
  return v === null || typeof v === 'string';
}

function isDashboardFilters(value: unknown): value is DashboardFilters {
  if (typeof value !== 'object' || value === null) return false;
  if (!('businessId' in value) || !('productId' in value) || !('teamId' in value)) return false;
  return (
    isNullOrString(value.businessId) &&
    isNullOrString(value.productId) &&
    isNullOrString(value.teamId)
  );
}

function loadFilters(): DashboardFilters {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY_FILTERS;
    const parsed: unknown = JSON.parse(raw);
    return isDashboardFilters(parsed) ? parsed : EMPTY_FILTERS;
  } catch {
    return EMPTY_FILTERS;
  }
}

function saveFilters(filters: DashboardFilters) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
}

const COLUMNS: Array<{ status: TaskStatus; title: string }> = [
  { status: 'backlog', title: 'Backlog' },
  { status: 'in_progress', title: 'In Progress' },
  { status: 'awaiting_user', title: 'Ждёт решения' },
];

export function Dashboard() {
  const { addToast } = useToast();
  const [filters, setFilters] = useState<DashboardFilters>(loadFilters);
  const [showDone, setShowDone] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [activeDragTask, setActiveDragTask] = useState<Task | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  const { data: businesses } = useBusinesses();
  const { data: products } = useProducts(filters.businessId ?? '');
  const { data: teams } = useTeams();
  const { data: tasks, isLoading: tasksLoading } = useTasks(filters.productId);
  const createTask = useCreateTask();
  const updateTaskStatus = useUpdateTaskStatus();

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  );

  useEffect(() => { saveFilters(filters); }, [filters]);

  const handleBusinessChange = useCallback((businessId: string) => {
    setFilters((prev) => ({ businessId: businessId || null, productId: null, teamId: prev.teamId }));
  }, []);

  const handleProductChange = useCallback((productId: string) => {
    setFilters((prev) => ({ ...prev, productId: productId || null }));
  }, []);

  const handleTeamChange = useCallback((teamId: string) => {
    setFilters((prev) => ({ ...prev, teamId: teamId || null }));
  }, []);

  const tasksByStatus = useMemo(() => {
    const grouped: Record<TaskStatus, Task[]> = {
      backlog: [], in_progress: [], awaiting_user: [], done: [], error: [],
    };
    if (!tasks) return grouped;
    const filtered = filters.teamId ? tasks.filter((t) => t.team_id === filters.teamId) : tasks;
    for (const task of filtered) { grouped[task.status].push(task); }
    return grouped;
  }, [tasks, filters.teamId]);

  const hasErrorTasks = tasksByStatus.error.length > 0;

  function handleDragStart(event: DragStartEvent) {
    const maybeTask: unknown = event.active.data.current?.task;
    setActiveDragTask(isTask(maybeTask) ? maybeTask : null);
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveDragTask(null);
    const { active, over } = event;
    if (!over) return;

    const maybeTask: unknown = active.data.current?.task;
    const maybeStatus: unknown = over.data.current?.status;
    if (!isTask(maybeTask) || !isTaskStatus(maybeStatus)) return;
    if (maybeTask.status === maybeStatus) return;

    if (!isTransitionAllowed(maybeTask.status, maybeStatus)) {
      const errorMsg = getTransitionError(maybeTask.status, maybeStatus);
      if (errorMsg) addToast({ type: "error", title: "Недопустимый переход", message: errorMsg });
      return;
    }

    if (maybeTask.status === 'backlog' && maybeStatus === 'in_progress' && !maybeTask.product_id) {
      addToast({ type: "warning", title: "Невозможно запустить", message: "Задача должна иметь привязку к продукту" });
      return;
    }

    updateTaskStatus.mutate(
      { id: maybeTask.id, status: maybeStatus },
      { onError: (err: Error) => addToast({ type: "error", title: "Ошибка", message: err.message }) },
    );
  }

  function handleStartTask(taskId: string) {
    updateTaskStatus.mutate(
      { id: taskId, status: 'in_progress' },
      { onError: (err: Error) => addToast({ type: "error", title: "Ошибка", message: err.message }) },
    );
  }

  function handleTaskClick(task: Task) {
    setSelectedTaskId(task.id);
  }

  const filtersSelected = !!filters.businessId && !!filters.productId;

  return (
    <div className="flex flex-col h-full">
      <FilterBar
        businesses={businesses ?? []}
        products={products ?? []}
        teams={teams ?? []}
        filters={filters}
        onBusinessChange={handleBusinessChange}
        onProductChange={handleProductChange}
        onTeamChange={handleTeamChange}
      />

      {!filtersSelected && (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-gray-400 text-sm">Выберите бизнес и продукт, чтобы увидеть задачи</p>
        </div>
      )}

      {filtersSelected && tasksLoading && (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-gray-400 text-sm">Загрузка задач...</p>
        </div>
      )}

      {filtersSelected && !tasksLoading && (
        <KanbanBoard
          columns={COLUMNS}
          tasksByStatus={tasksByStatus}
          showDone={showDone}
          hasErrorTasks={hasErrorTasks}
          activeDragTask={activeDragTask}
          sensors={sensors}
          onShowDoneChange={setShowDone}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onTaskClick={handleTaskClick}
          onStartTask={handleStartTask}
          onAddClick={() => setShowCreateModal(true)}
        />
      )}

      {showCreateModal && filters.productId && (
        <CreateTaskModal
          productId={filters.productId}
          isLoading={createTask.isPending}
          onSubmit={(data) => {
            createTask.mutate(data, {
              onSuccess: () => setShowCreateModal(false),
              onError: (err: Error) => addToast({ type: "error", title: "Ошибка", message: err.message }),
            });
          }}
          onClose={() => setShowCreateModal(false)}
        />
      )}

      {selectedTaskId && (
        <TaskModal
          taskId={selectedTaskId}
          onClose={() => setSelectedTaskId(null)}
        />
      )}

    </div>
  );
}

// ── KanbanBoard (extracted to keep Dashboard under 200 lines) ────────────────

interface KanbanBoardProps {
  columns: Array<{ status: TaskStatus; title: string }>;
  tasksByStatus: Record<TaskStatus, Task[]>;
  showDone: boolean;
  hasErrorTasks: boolean;
  activeDragTask: Task | null;
  sensors: ReturnType<typeof useSensors>;
  onShowDoneChange: (show: boolean) => void;
  onDragStart: (event: DragStartEvent) => void;
  onDragEnd: (event: DragEndEvent) => void;
  onTaskClick: (task: Task) => void;
  onStartTask: (taskId: string) => void;
  onAddClick: () => void;
}

function KanbanBoard({
  columns, tasksByStatus, showDone, hasErrorTasks, activeDragTask,
  sensors, onShowDoneChange, onDragStart, onDragEnd,
  onTaskClick, onStartTask, onAddClick,
}: KanbanBoardProps) {
  return (
    <>
      <div className="flex items-center gap-3 px-4 py-2">
        <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer">
          <input
            type="checkbox"
            checked={showDone}
            onChange={(e) => onShowDoneChange(e.target.checked)}
            className="rounded"
          />
          Показать завершённые
        </label>
      </div>

      <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd}>
        <div className="flex-1 overflow-x-auto px-4 pb-4">
          <div className="flex gap-4 min-h-0">
            {columns.map((col) => (
              <KanbanColumn
                key={col.status}
                title={col.title}
                status={col.status}
                tasks={tasksByStatus[col.status]}
                onTaskClick={onTaskClick}
                onStartTask={col.status === 'backlog' ? onStartTask : undefined}
                showAddButton={col.status === 'backlog'}
                onAddClick={col.status === 'backlog' ? onAddClick : undefined}
              />
            ))}
            {showDone && (
              <KanbanColumn title="Готово" status="done" tasks={tasksByStatus.done} onTaskClick={onTaskClick} />
            )}
            {hasErrorTasks && (
              <KanbanColumn title="Ошибка" status="error" tasks={tasksByStatus.error} onTaskClick={onTaskClick} />
            )}
          </div>
        </div>
        <DragOverlay>
          {activeDragTask && <TaskCard task={activeDragTask} onClick={() => undefined} />}
        </DragOverlay>
      </DndContext>
    </>
  );
}
