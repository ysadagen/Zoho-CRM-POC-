import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { AppRouter } from '@/app/router';
import { clearSession } from '@/auth/token-storage';
import { renderWithProviders, seedSession } from '@/test/utils';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => {
  server.resetHandlers();
  clearSession();
});
afterAll(() => server.close());

const CUSTOMERS = [{ id: 'c1', company_name: 'Acme', is_active: true }];
const ITEMS = [{ id: 'i1', sku: 'FIN-1', name: 'Bottle 1L', unit_of_measure: 'pcs' }];
const SO_DRAFT = {
  id: 'so1',
  so_number: 'SO-202605-000001',
  customer_id: 'c1',
  order_date: '2026-05-10',
  expected_delivery_date: null,
  shipped_date: null,
  status: 'DRAFT',
  subtotal: '90',
  total: '90',
  notes: 'Trial dispatch',
  items: [{ id: 'l1', sales_order_id: 'so1', item_id: 'i1', quantity: '2', unit_price: '45', line_total: '90', created_at: '' }],
  created_at: '2026-05-10T00:00:00Z',
  updated_at: '2026-05-10T00:00:00Z',
};

function commonHandlers() {
  return [
    http.get(`${BASE}/customers`, () => HttpResponse.json({ items: CUSTOMERS, total: 1, limit: 100, offset: 0 })),
    http.get(`${BASE}/items`, () => HttpResponse.json({ items: ITEMS, total: 1, limit: 100, offset: 0 })),
  ];
}

describe('SalesOrderDetailPage', () => {
  it('shows the SO header and line items', async () => {
    server.use(...commonHandlers(), http.get(`${BASE}/sales-orders/so1`, () => HttpResponse.json(SO_DRAFT)));
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/sales-orders/so1' });

    expect(await screen.findByText('SO-202605-000001')).toBeInTheDocument();
    expect(await screen.findByText('Bottle 1L')).toBeInTheDocument();
    expect(screen.getByText('Trial dispatch')).toBeInTheDocument();
  });

  it('ships the SO through the confirmation modal', async () => {
    let shipped = false;
    server.use(
      ...commonHandlers(),
      http.get(`${BASE}/sales-orders/so1`, () => HttpResponse.json(SO_DRAFT)),
      http.post(`${BASE}/sales-orders/so1/ship`, () => {
        shipped = true;
        return HttpResponse.json({ ...SO_DRAFT, status: 'SHIPPED', shipped_date: '2026-05-12' });
      }),
    );
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/sales-orders/so1' });
    await screen.findByText('SO-202605-000001');

    await user.click(screen.getByRole('button', { name: 'Ship' }));
    const dialog = await screen.findByRole('dialog', { name: 'Ship SO-202605-000001' });
    await user.click(within(dialog).getByRole('button', { name: 'Confirm ship' }));

    await waitFor(() => expect(shipped).toBe(true));
    expect(await screen.findByText('Order shipped. Stock updated.')).toBeInTheDocument();
  });

  it('offers "Refresh stock" on 409 INSUFFICIENT_STOCK (§5)', async () => {
    server.use(
      ...commonHandlers(),
      http.get(`${BASE}/sales-orders/so1`, () => HttpResponse.json(SO_DRAFT)),
      http.post(`${BASE}/sales-orders/so1/ship`, () =>
        HttpResponse.json(
          { error: { code: 'INSUFFICIENT_STOCK', message: 'Insufficient stock: 1 available, 2 requested', request_id: 'req-is' } },
          { status: 409 },
        ),
      ),
    );
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/sales-orders/so1' });
    await screen.findByText('SO-202605-000001');

    await user.click(screen.getByRole('button', { name: 'Ship' }));
    const dialog = await screen.findByRole('dialog', { name: 'Ship SO-202605-000001' });
    await user.click(within(dialog).getByRole('button', { name: 'Confirm ship' }));

    const toast = (await screen.findByText(/Insufficient stock/)).closest('.toast');
    expect(toast).toHaveClass('danger');
    expect(toast).toHaveTextContent('Request ID: req-is');
    expect(within(toast as HTMLElement).getByRole('button', { name: 'Refresh stock' })).toBeInTheDocument();
  });

  it('shows a page error with the Request ID when the SO fails to load', async () => {
    server.use(
      ...commonHandlers(),
      http.get(`${BASE}/sales-orders/so1`, () =>
        HttpResponse.json(
          { error: { code: 'SALES_ORDER_NOT_FOUND', message: 'Not found', request_id: 'req-so404' } },
          { status: 404 },
        ),
      ),
    );
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/sales-orders/so1' });
    await waitFor(() => expect(screen.getByText(/Request ID: req-so404/)).toBeInTheDocument());
  });
});
