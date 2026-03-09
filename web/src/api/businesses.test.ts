import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  getBusinesses,
  getBusiness,
  createBusiness,
  updateBusiness,
  deleteBusiness,
  BusinessConflictError,
} from './businesses';

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

describe('businesses API', () => {
  it('getBusinesses fetches list', async () => {
    const list = [{ id: 'b-1', name: 'My Co', products_count: 2 }];
    mockFetch.mockResolvedValueOnce(jsonResponse(list));
    const result = await getBusinesses();
    expect(result).toEqual(list);
    expect(mockFetch).toHaveBeenCalledWith('/api/businesses', expect.anything());
  });

  it('getBusiness fetches by id', async () => {
    const business = { id: 'b-1', name: 'My Co', products_count: 0 };
    mockFetch.mockResolvedValueOnce(jsonResponse(business));
    const result = await getBusiness('b-1');
    expect(result).toEqual(business);
    expect(mockFetch).toHaveBeenCalledWith('/api/businesses/b-1', expect.anything());
  });

  it('createBusiness sends POST', async () => {
    const business = { id: 'b-2', name: 'New Co', products_count: 0 };
    mockFetch.mockResolvedValueOnce(jsonResponse(business));
    const result = await createBusiness({ name: 'New Co' });
    expect(result).toEqual(business);
    expect(mockFetch).toHaveBeenCalledWith('/api/businesses', expect.objectContaining({ method: 'POST' }));
  });

  it('updateBusiness sends PATCH', async () => {
    const business = { id: 'b-1', name: 'Updated Co', products_count: 0 };
    mockFetch.mockResolvedValueOnce(jsonResponse(business));
    const result = await updateBusiness('b-1', { name: 'Updated Co' });
    expect(result).toEqual(business);
    expect(mockFetch).toHaveBeenCalledWith('/api/businesses/b-1', expect.objectContaining({ method: 'PATCH' }));
  });

  it('deleteBusiness sends DELETE without force', async () => {
    mockFetch.mockResolvedValueOnce(emptyResponse());
    await deleteBusiness('b-1');
    expect(mockFetch).toHaveBeenCalledWith('/api/businesses/b-1', expect.objectContaining({ method: 'DELETE' }));
  });

  it('deleteBusiness with force appends query param', async () => {
    mockFetch.mockResolvedValueOnce(emptyResponse());
    await deleteBusiness('b-1', true);
    expect(mockFetch).toHaveBeenCalledWith('/api/businesses/b-1?force=true', expect.anything());
  });

  it('deleteBusiness throws BusinessConflictError on 409', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ products_count: 3 }, 409));
    await expect(deleteBusiness('b-1')).rejects.toBeInstanceOf(BusinessConflictError);
  });

  it('BusinessConflictError carries productsCount', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ products_count: 5 }, 409));
    const err = await deleteBusiness('b-1').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(BusinessConflictError);
    expect((err as BusinessConflictError).productsCount).toBe(5);
  });
});
