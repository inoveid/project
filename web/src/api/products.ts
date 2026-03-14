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

export interface ProductFile {
  name: string;
  type: 'file' | 'dir';
  size: number;
}

export function getProductFiles(id: string): Promise<ProductFile[]> {
  return fetchApi<ProductFile[]>(`/products/${id}/files`);
}

export interface FileEntry {
  name: string;
  path: string;
  type: 'file' | 'dir';
  size: number;
}

export interface FileContent {
  path: string;
  content: string;
  size: number;
}

export interface GitInfo {
  initialized: boolean;
  branch?: string;
  branches?: string[];
  commits?: Array<{ hash: string; message: string; author: string; date: string }>;
  changed_files?: number;
}

export function getFileTree(productId: string, path: string = ''): Promise<FileEntry[]> {
  const params = path ? `?path=${encodeURIComponent(path)}` : '';
  return fetchApi<FileEntry[]>(`/products/${productId}/files/tree${params}`);
}

export function readFile(productId: string, path: string): Promise<FileContent> {
  return fetchApi<FileContent>(`/products/${productId}/file?path=${encodeURIComponent(path)}`);
}

export function writeFile(productId: string, path: string, content: string): Promise<{ path: string; size: number }> {
  return fetchApi(`/products/${productId}/file?path=${encodeURIComponent(path)}`, {
    method: 'PUT',
    body: JSON.stringify({ content }),
  });
}

export function getGitInfo(productId: string): Promise<GitInfo> {
  return fetchApi<GitInfo>(`/products/${productId}/git/info`);
}
