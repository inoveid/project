import { fetchApi, BASE_URL } from './client';
import type { Business, BusinessCreate, BusinessUpdate } from '../types';

export class BusinessConflictError extends Error {
  constructor(public readonly productsCount: number) {
    super(`Business has ${productsCount} products. Use force to delete all.`);
    this.name = 'BusinessConflictError';
  }
}

function hasProductsCount(value: unknown): value is { products_count: number } {
  return (
    typeof value === 'object' &&
    value !== null &&
    'products_count' in value &&
    typeof (value as Record<string, unknown>).products_count === 'number'
  );
}

export function getBusinesses(): Promise<Business[]> {
  return fetchApi<Business[]>('/businesses');
}

export function getBusiness(id: string): Promise<Business> {
  return fetchApi<Business>(`/businesses/${id}`);
}

export function createBusiness(data: BusinessCreate): Promise<Business> {
  return fetchApi<Business>('/businesses', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateBusiness(id: string, data: BusinessUpdate): Promise<Business> {
  return fetchApi<Business>(`/businesses/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteBusiness(id: string, force = false): Promise<void> {
  const query = force ? '?force=true' : '';
  const response = await fetch(`${BASE_URL}/businesses/${id}${query}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
  });
  if (response.ok || response.status === 204) return;
  if (response.status === 409) {
    const body: unknown = await response.json();
    throw new BusinessConflictError(hasProductsCount(body) ? body.products_count : 0);
  }
  const text = await response.text();
  throw new Error(`API error ${response.status}: ${text}`);
}
