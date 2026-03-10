import { fetchApi } from './client';
import type { Task, TaskCreate, TaskUpdate, TaskStatus } from '../types';

export function getTasks(productId: string): Promise<Task[]> {
  return fetchApi<Task[]>(`/products/${productId}/tasks`);
}

export function getTask(id: string): Promise<Task> {
  return fetchApi<Task>(`/tasks/${id}`);
}

export function createTask(data: TaskCreate): Promise<Task> {
  return fetchApi<Task>('/tasks', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateTask(id: string, data: TaskUpdate): Promise<Task> {
  return fetchApi<Task>(`/tasks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteTask(id: string): Promise<void> {
  return fetchApi<void>(`/tasks/${id}`, { method: 'DELETE' });
}

export function updateTaskStatus(id: string, status: TaskStatus): Promise<Task> {
  return fetchApi<Task>(`/tasks/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}
