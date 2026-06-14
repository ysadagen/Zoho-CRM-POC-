import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { createAdjustment, listStockMovements } from './sm.api';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('sm.api', () => {
  it('listStockMovements forwards item/direction/reason filters', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/stock-movements`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, limit: 25, offset: 0 });
      }),
    );
    await listStockMovements({ limit: 25, offset: 0, item_id: 'i1', direction: 'IN', reason: 'ADJUSTMENT' });
    expect(url?.searchParams.get('item_id')).toBe('i1');
    expect(url?.searchParams.get('direction')).toBe('IN');
    expect(url?.searchParams.get('reason')).toBe('ADJUSTMENT');
  });

  it('createAdjustment posts to /adjustments', async () => {
    let body: unknown;
    server.use(
      http.post(`${BASE}/stock-movements/adjustments`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: 'm-new', item_id: 'i1', direction: 'IN' }, { status: 201 });
      }),
    );
    const movement = await createAdjustment({ item_id: 'i1', direction: 'IN', quantity: '5', remarks: 'Recount correction' });
    expect(movement.id).toBe('m-new');
    expect(body).toMatchObject({ item_id: 'i1', direction: 'IN', remarks: 'Recount correction' });
  });
});
