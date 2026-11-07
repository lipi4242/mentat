// Refine DataProvider — reads and writes. The owner writes from
// this UI, so create and update are implemented. Needs are archived, not
// deleted, so deleteOne always rejects.
//
// The worker's list endpoints have no pagination (see worker/src/core/crud.ts)
// — they return the whole array plus an `X-Total-Count`. So getList sends no
// paging/sort/filter params: there is nothing on the other side to read them,
// and antd paginates the full array client-side.
import type { DataProvider } from '@refinedev/core';
import { apiUrl } from './config';
import { ApiError, requestJson } from './lib/api';

const idPath = (resource: string, id: unknown) =>
  `/api/${resource}/${encodeURIComponent(String(id))}`;

export const dataProvider: DataProvider = {
  getApiUrl: () => apiUrl('/api'),
  async getList({ resource }) {
    const data = await requestJson<unknown>('GET', `/api/${resource}`);
    // An empty body means "no rows"; anything that is not an array is a
    // broken contract and must surface as an error rather than as a raw
    // `Cannot read properties of null (reading 'length')`.
    if (data == null) return { data: [], total: 0 };
    if (!Array.isArray(data)) throw new ApiError(500);
    return { data: data as any, total: data.length };
  },
  async getOne({ resource, id }) {
    return { data: await requestJson<any>('GET', idPath(resource, id)) };
  },
  async create({ resource, variables }) {
    return { data: await requestJson<any>('POST', `/api/${resource}`, variables ?? null) };
  },
  async update({ resource, id, variables }) {
    return { data: await requestJson<any>('PATCH', idPath(resource, id), variables ?? null) };
  },
  deleteOne: () => Promise.reject(new Error('needs are archived, not deleted')),
};
