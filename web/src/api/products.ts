import { fetchApi } from './client';
import type { Product, ProductCreate, ProductUpdate } from '../types';

export function getProducts(businessId: string): Promise<Product[]> {
  return fetchApi<Product[]>(`/products?business_id=${businessId}`);
}

export function getProduct(id: string): Promise<Product> {
  return fetchApi<Product>(`/products/${id}`);
}

export function createProduct(data: ProductCreate): Promise<Product> {
  return fetchApi<Product>('/products', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateProduct(id: string, data: ProductUpdate): Promise<Product> {
  return fetchApi<Product>(`/products/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteProduct(id: string): Promise<void> {
  return fetchApi<void>(`/products/${id}`, { method: 'DELETE' });
}

export function cloneProduct(id: string): Promise<Product> {
  return fetchApi<Product>(`/products/${id}/clone`, { method: 'POST' });
}
