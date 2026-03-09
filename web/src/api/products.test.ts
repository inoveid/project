import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  getProducts,
  getProduct,
  createProduct,
  updateProduct,
  deleteProduct,
  cloneProduct,
} from './products';

const mockFetch = vi.fn();
globalThis.fetch = mockFetch as typeof fetch;

function jsonResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  };
}

function emptyResponse() {
  return { ok: true, status: 204, json: () => Promise.resolve(undefined), text: () => Promise.resolve('') };
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe('products API', () => {
  it('getProducts fetches by businessId', async () => {
    const list = [{ id: 'p-1', name: 'SaaS', business_id: 'b-1' }];
    mockFetch.mockResolvedValueOnce(jsonResponse(list));
    const result = await getProducts('b-1');
    expect(result).toEqual(list);
    expect(mockFetch).toHaveBeenCalledWith('/api/products?business_id=b-1', expect.anything());
  });

  it('getProduct fetches by id', async () => {
    const product = { id: 'p-1', name: 'SaaS', status: 'ready' };
    mockFetch.mockResolvedValueOnce(jsonResponse(product));
    const result = await getProduct('p-1');
    expect(result).toEqual(product);
    expect(mockFetch).toHaveBeenCalledWith('/api/products/p-1', expect.anything());
  });

  it('createProduct sends POST', async () => {
    const product = { id: 'p-2', name: 'New App', business_id: 'b-1' };
    mockFetch.mockResolvedValueOnce(jsonResponse(product));
    const result = await createProduct({ name: 'New App', business_id: 'b-1' });
    expect(result).toEqual(product);
    expect(mockFetch).toHaveBeenCalledWith('/api/products', expect.objectContaining({ method: 'POST' }));
  });

  it('updateProduct sends PATCH', async () => {
    const product = { id: 'p-1', name: 'Updated', business_id: 'b-1' };
    mockFetch.mockResolvedValueOnce(jsonResponse(product));
    const result = await updateProduct('p-1', { name: 'Updated' });
    expect(result).toEqual(product);
    expect(mockFetch).toHaveBeenCalledWith('/api/products/p-1', expect.objectContaining({ method: 'PATCH' }));
  });

  it('deleteProduct sends DELETE', async () => {
    mockFetch.mockResolvedValueOnce(emptyResponse());
    await deleteProduct('p-1');
    expect(mockFetch).toHaveBeenCalledWith('/api/products/p-1', expect.objectContaining({ method: 'DELETE' }));
  });

  it('cloneProduct sends POST to /clone', async () => {
    const product = { id: 'p-1', name: 'SaaS', status: 'cloning' };
    mockFetch.mockResolvedValueOnce(jsonResponse(product));
    const result = await cloneProduct('p-1');
    expect(result).toEqual(product);
    expect(mockFetch).toHaveBeenCalledWith('/api/products/p-1/clone', expect.objectContaining({ method: 'POST' }));
  });
});
