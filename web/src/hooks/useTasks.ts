import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createTask,
  deleteTask,
  getTask,
  getTasks,
  updateTask,
  updateTaskStatus,
} from '../api/tasks';
import { getSessionsByTask } from '../api/sessions';
import type { TaskCreate, TaskUpdate, TaskStatus } from '../types';

const TASKS_KEY = ['tasks'] as const;

export function useTasks(productId: string | null) {
  return useQuery({
    queryKey: [...TASKS_KEY, productId],
    queryFn: () => getTasks(productId!),
    enabled: !!productId,
  });
}

export function useTask(id: string) {
  return useQuery({
    queryKey: [...TASKS_KEY, 'detail', id],
    queryFn: () => getTask(id),
    enabled: !!id,
    refetchInterval: (query) =>
      query.state.data?.status === 'awaiting_user' ? 3000 : false,
  });
}

export function useTaskSessions(taskId: string, taskStatus?: TaskStatus) {
  const isActive = taskStatus === 'in_progress' || taskStatus === 'awaiting_user';
  return useQuery({
    queryKey: ['sessions', 'by-task', taskId],
    queryFn: () => getSessionsByTask(taskId),
    enabled: !!taskId,
    refetchInterval: isActive ? 5000 : false,
  });
}

export function useCreateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: TaskCreate) => createTask(data),
    onSuccess: (task) => {
      void queryClient.invalidateQueries({ queryKey: [...TASKS_KEY, task.product_id] });
    },
  });
}

export function useUpdateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TaskUpdate }) => updateTask(id, data),
    onSuccess: (task) => {
      void queryClient.invalidateQueries({ queryKey: [...TASKS_KEY, task.product_id] });
      void queryClient.invalidateQueries({ queryKey: [...TASKS_KEY, 'detail', task.id] });
    },
  });
}

export function useDeleteTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id: string; productId: string }) => deleteTask(vars.id),
    onSuccess: (_, { productId }) => {
      void queryClient.invalidateQueries({ queryKey: [...TASKS_KEY, productId] });
    },
  });
}

export function useUpdateTaskStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: TaskStatus }) => updateTaskStatus(id, status),
    onSuccess: (task) => {
      void queryClient.invalidateQueries({ queryKey: [...TASKS_KEY, task.product_id] });
      void queryClient.invalidateQueries({ queryKey: [...TASKS_KEY, 'detail', task.id] });
    },
  });
}
