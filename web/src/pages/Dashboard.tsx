import { useCallback, useEffect, useMemo, useState } from 'react';
import { DndContext, DragEndEvent, DragOverlay, DragStartEvent, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { useBusinesses } from '../hooks/useBusinesses';
import { useProducts } from '../hooks/useProducts';
import { useTeams } from '../hooks/useTeams';
import { useTasks, useCreateTask, useUpdateTaskStatus } from '../hooks/useTasks';
import { KanbanColumn } from '../components/tasks/KanbanColumn';
import { TaskCard } from '../components/tasks/TaskCard';
import { CreateTaskModal } from '../components/tasks/CreateTaskModal';
import { ToastContainer, showToast } from '../components/tasks/Toast';
import { isTransitionAllowed, getTransitionError } from '../components/tasks/statusConfig';
import type { Task, TaskStatus } from '../types';

const STORAGE_KEY = 'dashboard_filters';

interface DashboardFilters {
  businessId: string | null;
  productId: string | null;
  teamId: string | null;
}

function loadFilters(): DashboardFilters {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { businessId: null, productId: null, teamId: null };
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null) {
      return { businessId: null, productId: null, teamId: null };
    }
    const obj = parsed as Record<string, unknown>;
    return {
      businessId: typeof obj.businessId === 'string' ? obj.businessId : null,
      productId: typeof obj.productId === 'string' ? obj.productId : null,
      teamId: typeof obj.teamId === 'string' ? obj.teamId : null,
    };
  } catch {
    return { businessId: null, productId: null, teamId: null };
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
  const [filters, setFilters] = useState<DashboardFilters>(loadFilters);
  const [showDone, setShowDone] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [activeDragTask, setActiveDragTask] = useState<Task | null>(null);

  const { data: businesses } = useBusinesses();
  const { data: products } = useProducts(filters.businessId ?? '');
  const { data: teams } = useTeams();
  const { data: tasks, isLoading: tasksLoading } = useTasks(filters.productId);
  const createTask = useCreateTask();
  const updateTaskStatus = useUpdateTaskStatus();

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  );

  useEffect(() => {
    saveFilters(filters);
  }, [filters]);

  // Reset product when business changes
  const handleBusinessChange = useCallback((businessId: string) => {
    setFilters({ businessId: businessId || null, productId: null, teamId: filters.teamId });
  }, [filters.teamId]);

  const handleProductChange = useCallback((productId: string) => {
    setFilters((prev) => ({ ...prev, productId: productId || null }));
  }, []);

  const handleTeamChange = useCallback((teamId: string) => {
    setFilters((prev) => ({ ...prev, teamId: teamId || null }));
  }, []);

  // Group tasks by status
  const tasksByStatus = useMemo(() => {
    const grouped: Record<TaskStatus, Task[]> = {
      backlog: [],
      in_progress: [],
      awaiting_user: [],
      done: [],
      error: [],
    };
    if (!tasks) return grouped;

    const filteredTasks = filters.teamId
      ? tasks.filter((t) => t.team_id === filters.teamId)
      : tasks;

    for (const task of filteredTasks) {
      grouped[task.status].push(task);
    }
    return grouped;
  }, [tasks, filters.teamId]);

  const hasErrorTasks = tasksByStatus.error.length > 0;

  // Drag handlers
  function handleDragStart(event: DragStartEvent) {
    const task = event.active.data.current?.task as Task | undefined;
    setActiveDragTask(task ?? null);
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveDragTask(null);
    const { active, over } = event;
    if (!over) return;

    const task = active.data.current?.task as Task | undefined;
    const targetStatus = over.data.current?.status as TaskStatus | undefined;
    if (!task || !targetStatus || task.status === targetStatus) return;

    if (!isTransitionAllowed(task.status, targetStatus)) {
      const errorMsg = getTransitionError(task.status, targetStatus);
      if (errorMsg) showToast(errorMsg);
      return;
    }

    // Backlog → in_progress requires valid task
    if (task.status === 'backlog' && targetStatus === 'in_progress' && !task.product_id) {
      showToast('Задача должна иметь привязку к продукту');
      return;
    }

    updateTaskStatus.mutate(
      { id: task.id, status: targetStatus },
      {
        onError: (err: Error) => {
          showToast(`Ошибка: ${err.message}`);
        },
      },
    );
  }

  function handleStartTask(taskId: string) {
    updateTaskStatus.mutate(
      { id: taskId, status: 'in_progress' },
      {
        onError: (err: Error) => showToast(`Ошибка: ${err.message}`),
      },
    );
  }

  function handleTaskClick(_task: Task) {
    // Заглушка до TASK-047
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
          <p className="text-gray-400 text-sm">
            Выберите бизнес и продукт, чтобы увидеть задачи
          </p>
        </div>
      )}

      {filtersSelected && tasksLoading && (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-gray-400 text-sm">Загрузка задач...</p>
        </div>
      )}

      {filtersSelected && !tasksLoading && (
        <>
          <div className="flex items-center gap-3 px-4 py-2">
            <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer">
              <input
                type="checkbox"
                checked={showDone}
                onChange={(e) => setShowDone(e.target.checked)}
                className="rounded"
              />
              Показать завершённые
            </label>
          </div>

          <DndContext
            sensors={sensors}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <div className="flex-1 overflow-x-auto px-4 pb-4">
              <div className="flex gap-4 min-h-0">
                {COLUMNS.map((col) => (
                  <KanbanColumn
                    key={col.status}
                    title={col.title}
                    status={col.status}
                    tasks={tasksByStatus[col.status]}
                    onTaskClick={handleTaskClick}
                    onStartTask={col.status === 'backlog' ? handleStartTask : undefined}
                    showAddButton={col.status === 'backlog'}
                    onAddClick={col.status === 'backlog' ? () => setShowCreateModal(true) : undefined}
                  />
                ))}

                {showDone && (
                  <KanbanColumn
                    title="Готово"
                    status="done"
                    tasks={tasksByStatus.done}
                    onTaskClick={handleTaskClick}
                  />
                )}

                {hasErrorTasks && (
                  <KanbanColumn
                    title="Ошибка"
                    status="error"
                    tasks={tasksByStatus.error}
                    onTaskClick={handleTaskClick}
                  />
                )}
              </div>
            </div>

            <DragOverlay>
              {activeDragTask && (
                <TaskCard
                  task={activeDragTask}
                  onClick={() => undefined}
                />
              )}
            </DragOverlay>
          </DndContext>
        </>
      )}

      {showCreateModal && filters.productId && (
        <CreateTaskModal
          productId={filters.productId}
          isLoading={createTask.isPending}
          onSubmit={(data) => {
            createTask.mutate(data, {
              onSuccess: () => setShowCreateModal(false),
              onError: (err: Error) => showToast(`Ошибка: ${err.message}`),
            });
          }}
          onClose={() => setShowCreateModal(false)}
        />
      )}

      <ToastContainer />
    </div>
  );
}

// ── FilterBar ────────────────────────────────────────────────────────────────

interface FilterBarProps {
  businesses: Array<{ id: string; name: string }>;
  products: Array<{ id: string; name: string }>;
  teams: Array<{ id: string; name: string }>;
  filters: DashboardFilters;
  onBusinessChange: (id: string) => void;
  onProductChange: (id: string) => void;
  onTeamChange: (id: string) => void;
}

function FilterBar({
  businesses,
  products,
  teams,
  filters,
  onBusinessChange,
  onProductChange,
  onTeamChange,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-gray-200 bg-white">
      <Select
        label="Business"
        value={filters.businessId ?? ''}
        options={businesses.map((b) => ({ value: b.id, label: b.name }))}
        onChange={onBusinessChange}
        placeholder="Выбрать..."
      />

      <Select
        label="Product"
        value={filters.productId ?? ''}
        options={products.map((p) => ({ value: p.id, label: p.name }))}
        onChange={onProductChange}
        placeholder="Выбрать..."
        disabled={!filters.businessId}
      />

      <Select
        label="Team"
        value={filters.teamId ?? ''}
        options={teams.map((t) => ({ value: t.id, label: t.name }))}
        onChange={onTeamChange}
        placeholder="Все"
      />
    </div>
  );
}

// ── Select helper ────────────────────────────────────────────────────────────

interface SelectProps {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
  placeholder: string;
  disabled?: boolean;
}

function Select({ label, value, options, onChange, placeholder, disabled }: SelectProps) {
  return (
    <label className="flex items-center gap-1.5 text-sm text-gray-600">
      {label}:
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-400"
      >
        <option value="">{placeholder}</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}
