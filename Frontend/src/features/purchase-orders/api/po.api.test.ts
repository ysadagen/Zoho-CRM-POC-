import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import {
  createPurchaseOrder,
  getPurchaseOrder,
  listPurchaseOrders,
  receivePurchaseOrder,
} from './po.api';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('po.api', () => {
  it('listPurchaseOrders forwards status + vendor filters', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/purchase-orders`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, limit: 25, offset: 0 });
      }),
    );
    await listPurchaseOrders({ limit: 25, offset: 0, status: 'DRAFT', vendor_id: 'v1' });
    expect(url?.searchParams.get('status')).toBe('DRAFT');
    expect(url?.searchParams.get('vendor_id')).toBe('v1');
  });

  it('getPurchaseOrder fetches by id', async () => {
    server.use(http.get(`${BASE}/purchase-orders/po1`, () => HttpResponse.json({ id: 'po1' })));
    expect((await getPurchaseOrder('po1')).id).toBe('po1');
  });

  it('createPurchaseOrder posts the body', async () => {
    let body: unknown;
    server.use(
      http.post(`${BASE}/purchase-orders`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: 'po-new', po_number: 'PO-1' }, { status: 201 });
      }),
    );
    const po = await createPurchaseOrder({ vendor_id: 'v1', items: [{ item_id: 'i1', quantity: '100' }] });
    expect(po.id).toBe('po-new');
    expect(body).toMatchObject({ vendor_id: 'v1' });
  });

  it('receivePurchaseOrder POSTs to /receive with no body', async () => {
    let hit = false;
    server.use(
      http.post(`${BASE}/purchase-orders/po1/receive`, () => {
        hit = true;
        return HttpResponse.json({ id: 'po1', status: 'RECEIVED' });
      }),
    );
    const po = await receivePurchaseOrder('po1');
    expect(hit).toBe(true);
    expect(po.status).toBe('RECEIVED');
  });
});
