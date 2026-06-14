import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import {
  fetchDashboardItems,
  fetchDraftPurchaseOrderCount,
  fetchDraftSalesOrderCount,
  fetchRecentMovements,
} from './dashboard.api';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('dashboard.api', () => {
  it('fetchDashboardItems requests up to 100 items and returns the array', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/items`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [{ id: 'i1' }], total: 1, limit: 100, offset: 0 });
      }),
    );

    const items = await fetchDashboardItems();
    expect(url?.searchParams.get('limit')).toBe('100');
    expect(items).toEqual([{ id: 'i1' }]);
  });

  it('fetchRecentMovements requests the 5 most recent and returns the array', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/stock-movements`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [{ id: 'm1' }], total: 1, limit: 5, offset: 0 });
      }),
    );

    const movements = await fetchRecentMovements();
    expect(url?.searchParams.get('limit')).toBe('5');
    expect(movements).toEqual([{ id: 'm1' }]);
  });

  it('fetchDraftPurchaseOrderCount filters DRAFT and returns the pagination total', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/purchase-orders`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [], total: 12, limit: 1, offset: 0 });
      }),
    );

    const count = await fetchDraftPurchaseOrderCount();
    expect(url?.searchParams.get('status')).toBe('DRAFT');
    expect(url?.searchParams.get('limit')).toBe('1');
    expect(count).toBe(12);
  });

  it('fetchDraftSalesOrderCount filters DRAFT and returns the pagination total', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/sales-orders`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [], total: 8, limit: 1, offset: 0 });
      }),
    );

    const count = await fetchDraftSalesOrderCount();
    expect(url?.searchParams.get('status')).toBe('DRAFT');
    expect(count).toBe(8);
  });
});
