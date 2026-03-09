import { fetchApi } from './client';
import type { Product, ProductCreate, ProductUpdate } from '../types';

export function getProducts(businessId: string): Promise<Product[]> {
  return fetchApi<Product[]>(`/businesses/${businessId}/products`);
}

export function getProduct(id: string): Promise<Product> {
  return fetchApi<Product>(`/products/${id}`);
}

export function createProduct(data: ProductCreate): Promise<Product> {
  const { business_id, ...rest } = data;
  return fetchApi<Product>(`/businesses/${business_id}/products`, {
    method: 'POST',
    body: JSON.stringify(rest),
  });
}

export function updateProduct(id: string, data: ProductUpdate): Promise<Product> {
  return fetchApi<Product>(`/products/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteProduct(id: string): Promise<void> {
  return fetchApi<void>(`/products/${id}`, { method: 'DELETE' });
}

export function cloneProduct(id: string): Promise<Product> {
  return fetchApi<Product>(`/products/${id}/clone`, { method: 'POST' });
}
