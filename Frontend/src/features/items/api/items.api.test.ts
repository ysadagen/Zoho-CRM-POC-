import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import {
  createItem,
  getItem,
  listItemMovements,
  listItems,
  updateItem,
} from './items.api';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('items.api', () => {
  it('listItems forwards pagination + filters and drops empties', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/items`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, limit: 25, offset: 0 });
      }),
    );

    await listItems({ limit: 25, offset: 50, type: 'RAW', search: '  bottle  ' });
    expect(url?.searchParams.get('limit')).toBe('25');
    expect(url?.searchParams.get('offset')).toBe('50');
    expect(url?.searchParams.get('type')).toBe('RAW');
    expect(url?.searchParams.get('search')).toBe('bottle');
  });

  it('listItems omits empty type/search', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/items`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, limit: 25, offset: 0 });
      }),
    );

    await listItems({ limit: 25, offset: 0, search: '   ' });
    expect(url?.searchParams.has('type')).toBe(false);
    expect(url?.searchParams.has('search')).toBe(false);
  });

  it('getItem fetches by id', async () => {
    server.use(http.get(`${BASE}/items/i1`, () => HttpResponse.json({ id: 'i1', name: 'X' })));
    const item = await getItem('i1');
    expect(item.id).toBe('i1');
  });

  it('createItem posts the body and returns the minimal envelope', async () => {
    let body: unknown;
    server.use(
      http.post(`${BASE}/items`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          { id: 'new', sku: 'BOT-1L', name: '1L Bottle', created_at: 'now' },
          { status: 201 },
        );
      }),
    );

    const created = await createItem({
      sku: 'BOT-1L',
      name: '1L Bottle',
      type: 'FINISHED',
      category: 'Bottles',
      unit_of_measure: 'pcs',
      unit_price: '45',
    });
    expect(body).toMatchObject({ sku: 'BOT-1L', type: 'FINISHED' });
    expect(created.id).toBe('new');
  });

  it('updateItem patches by id', async () => {
    let body: unknown;
    server.use(
      http.patch(`${BASE}/items/i1`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: 'i1', name: 'Renamed' });
      }),
    );

    const item = await updateItem('i1', { name: 'Renamed' });
    expect(body).toEqual({ name: 'Renamed' });
    expect(item.name).toBe('Renamed');
  });

  it('listItemMovements filters by item_id', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BASE}/stock-movements`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 });
      }),
    );

    await listItemMovements('i1');
    expect(url?.searchParams.get('item_id')).toBe('i1');
    expect(url?.searchParams.get('limit')).toBe('50');
  });
});
