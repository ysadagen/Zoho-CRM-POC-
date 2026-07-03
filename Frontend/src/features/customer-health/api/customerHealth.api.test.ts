import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { getCustomerHealth, listCustomerHealth } from './customerHealth.api';

const BASE = 'http://localhost:8002/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const EMPTY_LIST = { items: [], total: 0, limit: 25, offset: 0, last_computed_at: null };

describe('customerHealth.api', () => {
  it('listCustomerHealth hits the Intelligence endpoint and parses', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/intelligence/customer-health`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [{ customer_id: 'c1' }], total: 1, limit: 25, offset: 0, last_computed_at: '2026-07-03T08:00:00Z' });
      }),
    );

    const res = await listCustomerHealth();
    expect(url?.searchParams.has('classification')).toBe(false);
    expect(url?.searchParams.has('limit')).toBe(false);
    expect(res.total).toBe(1);
    expect(res.items[0]?.customer_id).toBe('c1');
  });

  it('listCustomerHealth forwards the classification filter', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/intelligence/customer-health`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json(EMPTY_LIST);
      }),
    );

    await listCustomerHealth({ classification: 'AT_RISK' });
    expect(url?.searchParams.get('classification')).toBe('AT_RISK');
  });

  it('listCustomerHealth forwards limit and offset', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/intelligence/customer-health`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json(EMPTY_LIST);
      }),
    );

    await listCustomerHealth({ limit: 10, offset: 20 });
    expect(url?.searchParams.get('limit')).toBe('10');
    expect(url?.searchParams.get('offset')).toBe('20');
  });

  it('getCustomerHealth fetches by id from the Intelligence endpoint', async () => {
    server.use(
      http.get(`${BASE}/intelligence/customer-health/c1`, () =>
        HttpResponse.json({ customer_id: 'c1', company_name: 'Acme' }),
      ),
    );

    const detail = await getCustomerHealth('c1');
    expect(detail.customer_id).toBe('c1');
    expect(detail.company_name).toBe('Acme');
  });
});
