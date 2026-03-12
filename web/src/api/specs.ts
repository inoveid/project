import { fetchApi } from './client';
import type { Spec, SpecCreate, SpecUpdate, SpecVersion } from '../types';

export function getSpecs(productId: string): Promise<Spec[]> {
  return fetchApi<Spec[]>(`/products/${productId}/specs`);
}

export function getSpec(id: string): Promise<Spec> {
  return fetchApi<Spec>(`/specs/${id}`);
}

export function createSpec(productId: string, data: SpecCreate): Promise<Spec> {
  return fetchApi<Spec>(`/products/${productId}/specs`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateSpec(id: string, data: SpecUpdate): Promise<Spec> {
  return fetchApi<Spec>(`/specs/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteSpec(id: string): Promise<void> {
  return fetchApi<void>(`/specs/${id}`, { method: 'DELETE' });
}

export function getSpecVersions(specId: string): Promise<SpecVersion[]> {
  return fetchApi<SpecVersion[]>(`/specs/${specId}/versions`);
}

export function rollbackSpec(specId: string, version: number): Promise<Spec> {
  return fetchApi<Spec>(`/specs/${specId}/versions/${version}/rollback`, {
    method: 'POST',
  });
}
