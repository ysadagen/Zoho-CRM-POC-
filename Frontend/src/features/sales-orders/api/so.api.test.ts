import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { createSalesOrder, getSalesOrder, listSalesOrders, shipSalesOrder } from './so.api';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('so.api', () => {
  it('listSalesOrders forwards status + customer filters', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/sales-orders`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, limit: 25, offset: 0 });
      }),
    );
    await listSalesOrders({ limit: 25, offset: 0, status: 'DRAFT', customer_id: 'c1' });
    expect(url?.searchParams.get('status')).toBe('DRAFT');
    expect(url?.searchParams.get('customer_id')).toBe('c1');
  });

  it('getSalesOrder fetches by id', async () => {
    server.use(http.get(`${BASE}/sales-orders/so1`, () => HttpResponse.json({ id: 'so1' })));
    expect((await getSalesOrder('so1')).id).toBe('so1');
  });

  it('createSalesOrder posts the body', async () => {
    let body: unknown;
    server.use(
      http.post(`${BASE}/sales-orders`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: 'so-new', so_number: 'SO-1' }, { status: 201 });
      }),
    );
    const so = await createSalesOrder({ customer_id: 'c1', items: [{ item_id: 'i1', quantity: '5' }] });
    expect(so.id).toBe('so-new');
    expect(body).toMatchObject({ customer_id: 'c1' });
  });

  it('shipSalesOrder POSTs to /ship', async () => {
    let hit = false;
    server.use(
      http.post(`${BASE}/sales-orders/so1/ship`, () => {
        hit = true;
        return HttpResponse.json({ id: 'so1', status: 'SHIPPED' });
      }),
    );
    expect((await shipSalesOrder('so1')).status).toBe('SHIPPED');
    expect(hit).toBe(true);
  });
});
