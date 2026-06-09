import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { SalesOrdersListPage } from './SalesOrdersListPage';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const CUSTOMERS = [{ id: 'c1', company_name: 'Acme', is_active: true }];
const SO = {
  id: 'so1',
  so_number: 'SO-202605-000001',
  customer_id: 'c1',
  order_date: '2026-05-10',
  expected_delivery_date: null,
  shipped_date: null,
  status: 'DRAFT',
  subtotal: '90',
  total: '90',
  notes: null,
  items: [{ id: 'l1', sales_order_id: 'so1', item_id: 'i1', quantity: '2', unit_price: '45', line_total: '90', created_at: '' }],
  created_at: '2026-05-10T00:00:00Z',
  updated_at: '2026-05-10T00:00:00Z',
};

function handlers(onSoUrl?: (url: URL) => void) {
  return [
    http.get(`${BASE}/customers`, () => HttpResponse.json({ items: CUSTOMERS, total: 1, limit: 100, offset: 0 })),
    http.get(`${BASE}/sales-orders`, ({ request }) => {
      onSoUrl?.(new URL(request.url));
      return HttpResponse.json({ items: [SO], total: 1, limit: 25, offset: 0 });
    }),
    http.get(`${BASE}/items`, () =>
      HttpResponse.json({ items: [{ id: 'i1', sku: 'FIN-1', name: 'Bottle 1L', unit_of_measure: 'pcs' }], total: 1, limit: 100, offset: 0 }),
    ),
  ];
}

describe('SalesOrdersListPage', () => {
  it('lists SOs with the resolved customer name', async () => {
    server.use(...handlers());
    renderWithProviders(<SalesOrdersListPage />);
    expect(await screen.findByText('SO-202605-000001')).toBeInTheDocument();
    expect((await screen.findAllByText('Acme')).length).toBeGreaterThan(0);
  });

  it('sends the status filter to the server', async () => {
    const urls: URL[] = [];
    server.use(...handlers((url) => urls.push(url)));
    const user = userEvent.setup();
    renderWithProviders(<SalesOrdersListPage />);
    await screen.findByText('SO-202605-000001');

    await user.click(screen.getByRole('tab', { name: 'Shipped' }));
    await waitFor(() => expect(urls.at(-1)?.searchParams.get('status')).toBe('SHIPPED'));
  });

  it('opens the ship confirmation from an inline Ship', async () => {
    server.use(...handlers());
    const user = userEvent.setup();
    renderWithProviders(<SalesOrdersListPage />);
    await screen.findByText('SO-202605-000001');

    await user.click(screen.getByRole('button', { name: 'Ship' }));
    expect(await screen.findByRole('dialog', { name: 'Ship SO-202605-000001' })).toBeInTheDocument();
    expect(await screen.findByText('-2 pcs Bottle 1L')).toBeInTheDocument();
  });
});
