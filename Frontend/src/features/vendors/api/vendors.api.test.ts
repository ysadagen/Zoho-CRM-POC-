import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import {
  createVendorTerm,
  deleteVendorTerm,
  listVendorPurchaseOrders,
  listVendorTerms,
  listVendors,
  updateVendorTerm,
} from './vendors.api';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('vendors.api', () => {
  it('listVendors forwards trimmed search', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/vendors`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, limit: 25, offset: 0 });
      }),
    );
    await listVendors({ limit: 25, offset: 0, search: '  steel  ' });
    expect(url?.searchParams.get('search')).toBe('steel');
  });

  it('listVendorPurchaseOrders filters by vendor_id', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/purchase-orders`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 });
      }),
    );
    await listVendorPurchaseOrders('v1');
    expect(url?.searchParams.get('vendor_id')).toBe('v1');
  });

  it('listVendorTerms requests active terms under the vendor', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/vendors/v1/terms`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, limit: 100, offset: 0 });
      }),
    );
    await listVendorTerms('v1');
    expect(url?.searchParams.get('active_only')).toBe('true');
  });

  it('term create / update / delete hit the nested routes', async () => {
    let postBody: unknown;
    let patchBody: unknown;
    let deleted = false;
    server.use(
      http.post(`${BASE}/vendors/v1/terms`, async ({ request }) => {
        postBody = await request.json();
        return HttpResponse.json({ id: 't1', item_id: 'i1' }, { status: 201 });
      }),
      http.patch(`${BASE}/vendors/v1/terms/t1`, async ({ request }) => {
        patchBody = await request.json();
        return HttpResponse.json({ id: 't1', item_id: 'i1', rate: '160' });
      }),
      http.delete(`${BASE}/vendors/v1/terms/t1`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    await createVendorTerm('v1', { item_id: 'i1', rate: '150', effective_from: '2026-01-01' });
    expect(postBody).toMatchObject({ item_id: 'i1', rate: '150' });

    await updateVendorTerm('v1', 't1', { rate: '160' });
    expect(patchBody).toEqual({ rate: '160' });

    await deleteVendorTerm('v1', 't1');
    expect(deleted).toBe(true);
  });
});
