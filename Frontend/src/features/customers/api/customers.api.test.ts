import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import {
  createCustomer,
  getCustomer,
  listCustomerSalesOrders,
  listCustomers,
  updateCustomer,
} from './customers.api';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('customers.api', () => {
  it('listCustomers forwards pagination + trimmed search', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/customers`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, limit: 25, offset: 0 });
      }),
    );
    await listCustomers({ limit: 25, offset: 0, search: '  acme  ' });
    expect(url?.searchParams.get('search')).toBe('acme');
  });

  it('listCustomers omits empty search', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/customers`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, limit: 25, offset: 0 });
      }),
    );
    await listCustomers({ limit: 25, offset: 0, search: '   ' });
    expect(url?.searchParams.has('search')).toBe(false);
  });

  it('getCustomer / createCustomer / updateCustomer hit the right routes', async () => {
    let postBody: unknown;
    let patchBody: unknown;
    server.use(
      http.get(`${BASE}/customers/c1`, () => HttpResponse.json({ id: 'c1', company_name: 'Acme' })),
      http.post(`${BASE}/customers`, async ({ request }) => {
        postBody = await request.json();
        return HttpResponse.json({ id: 'new', company_name: 'Acme' }, { status: 201 });
      }),
      http.patch(`${BASE}/customers/c1`, async ({ request }) => {
        patchBody = await request.json();
        return HttpResponse.json({ id: 'c1', company_name: 'Renamed' });
      }),
    );

    expect((await getCustomer('c1')).id).toBe('c1');
    expect((await createCustomer({ company_name: 'Acme' })).id).toBe('new');
    expect(postBody).toMatchObject({ company_name: 'Acme' });
    expect((await updateCustomer('c1', { company_name: 'Renamed' })).company_name).toBe('Renamed');
    expect(patchBody).toEqual({ company_name: 'Renamed' });
  });

  it('listCustomerSalesOrders filters by customer_id', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/sales-orders`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 });
      }),
    );
    await listCustomerSalesOrders('c1');
    expect(url?.searchParams.get('customer_id')).toBe('c1');
  });
});
