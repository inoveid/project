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

export function checkoutBranch(productId: string, branch: string): Promise<{ branch: string }> {
  return fetchApi(`/products/${productId}/git/checkout`, {
    method: 'POST',
    body: JSON.stringify({ branch }),
  });
}

export function getGitDiff(productId: string): Promise<{ diff: string }> {
  return fetchApi(`/products/${productId}/git/diff`);
}

export interface DiffLine {
  type: "add" | "delete" | "context";
  content: string;
  old_no: number | null;
  new_no: number | null;
}

export interface DiffHunk {
  header: string;
  old_start: number;
  old_lines: number;
  new_start: number;
  new_lines: number;
  lines: DiffLine[];
}

export interface DiffFile {
  path: string;
  old_path: string | null;
  status: "modified" | "added" | "deleted" | "renamed" | "binary";
  additions: number;
  deletions: number;
  hunks: DiffHunk[];
}

export interface CommitDetail {
  hash: string;
  message: string;
  author: string;
  email: string;
  date: string;
  stats: string;
  diff: string;
  files: DiffFile[];
  total_additions: number;
  total_deletions: number;
}

export function getCommitDetail(productId: string, hash: string): Promise<CommitDetail> {
  return fetchApi<CommitDetail>(`/products/${productId}/git/commits/${hash}`);
}

export interface SyncStatus {
  has_remote: boolean;
  remote?: string;
  remote_url?: string;
  branch?: string;
  upstream?: string | null;
  ahead?: number;
  behind?: number;
  remote_branch_exists?: boolean;
  fetch_error?: string | null;
}

export function getSyncStatus(productId: string): Promise<SyncStatus> {
  return fetchApi<SyncStatus>(`/products/${productId}/git/sync-status`);
}

export function gitPush(productId: string): Promise<{ ok: boolean; message: string }> {
  return fetchApi(`/products/${productId}/git/push`, { method: 'POST' });
}

export function gitPull(productId: string): Promise<{ ok: boolean; message: string }> {
  return fetchApi(`/products/${productId}/git/pull`, { method: 'POST' });
}

export function addRemote(productId: string, url: string): Promise<{ ok: boolean; remote: string; url: string }> {
  return fetchApi(`/products/${productId}/git/remote`, {
    method: 'POST',
    body: JSON.stringify({ url }),
  });
}

export function createBranch(productId: string, name: string, fromBranch?: string): Promise<{ branch: string }> {
  return fetchApi(`/products/${productId}/git/branch`, {
    method: 'POST',
    body: JSON.stringify({ name, from_branch: fromBranch }),
  });
}

export interface SecretItem {
  id: string;
  key: string;
  has_value: boolean;
}

export function getSecrets(productId: string): Promise<SecretItem[]> {
  return fetchApi<SecretItem[]>(`/products/${productId}/secrets`);
}

export function saveSecret(productId: string, key: string, value: string): Promise<{ ok: boolean; key: string }> {
  return fetchApi(`/products/${productId}/secrets`, {
    method: 'POST',
    body: JSON.stringify({ key, value }),
  });
}

export function deleteSecret(productId: string, secretId: string): Promise<void> {
  return fetchApi<void>(`/products/${productId}/secrets/${secretId}`, { method: 'DELETE' });
}

export interface ChangedFile {
  path: string;
  status: 'modified' | 'added' | 'deleted' | 'untracked' | 'renamed';
  content_preview?: string;
}

export interface ChangesResult {
  files: ChangedFile[];
  diff_files: DiffFile[];
}

export function getChangedFiles(productId: string): Promise<ChangesResult> {
  return fetchApi<ChangesResult>(`/products/${productId}/git/changes`);
}

export function discardFile(productId: string, path: string): Promise<{ ok: boolean; path: string }> {
  return fetchApi(`/products/${productId}/git/discard`, {
    method: 'POST',
    body: JSON.stringify({ path }),
  });
}

export function gitCommit(productId: string, message: string): Promise<{ ok: boolean; message: string }> {
  return fetchApi(`/products/${productId}/git/commit`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}

export function renameBranch(productId: string, oldName: string, newName: string): Promise<{ ok: boolean }> {
  return fetchApi(`/products/${productId}/git/branch/rename`, {
    method: 'POST',
    body: JSON.stringify({ old_name: oldName, new_name: newName }),
  });
}

export function deleteBranch(productId: string, branchName: string): Promise<{ ok: boolean }> {
  return fetchApi(`/products/${productId}/git/branch/${encodeURIComponent(branchName)}`, {
    method: 'DELETE',
  });
}

export function mergeBranch(productId: string, source: string): Promise<{ ok: boolean; message: string }> {
  return fetchApi(`/products/${productId}/git/merge`, {
    method: 'POST',
    body: JSON.stringify({ source }),
  });
}
