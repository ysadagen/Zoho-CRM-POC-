import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { SalesOrderCreatePage } from './SalesOrderCreatePage';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const CUSTOMERS = [{ id: 'c1', company_name: 'Acme', is_active: true }];
const ITEMS = [
  { id: 'i1', sku: 'FIN-1', name: 'Bottle 1L', type: 'FINISHED', unit_of_measure: 'pcs', stock_quantity: '5', reorder_threshold: '0', unit_price: '45', status: 'IN_STOCK' },
];

function baseHandlers() {
  return [
    http.get(`${BASE}/customers`, () => HttpResponse.json({ items: CUSTOMERS, total: 1, limit: 100, offset: 0 })),
    http.get(`${BASE}/items`, () => HttpResponse.json({ items: ITEMS, total: 1, limit: 100, offset: 0 })),
  ];
}

describe('SalesOrderCreatePage', () => {
  it('validates customer and line items', async () => {
    server.use(...baseHandlers());
    const user = userEvent.setup();
    renderWithProviders(<SalesOrderCreatePage />);

    await screen.findByLabelText('Item for line 1');
    await user.click(screen.getByRole('button', { name: 'Create order' }));

    expect(await screen.findByText('Pick a customer')).toBeInTheDocument();
    expect(screen.getByText('Pick an item')).toBeInTheDocument();
    expect(screen.getByText('Qty required')).toBeInTheDocument();
  });

  it('shows a live stock chip and disables Create while a line is short (§5)', async () => {
    server.use(...baseHandlers());
    const user = userEvent.setup();
    renderWithProviders(<SalesOrderCreatePage />);

    await user.selectOptions(await screen.findByLabelText('Item for line 1'), 'i1');
    await user.type(screen.getByLabelText('Quantity for line 1'), '10');

    // Stock is 5 → ordering 10 is short by 5; Create must be disabled.
    expect(await screen.findByText(/short by 5/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create order' })).toBeDisabled();

    // Drop the qty within stock → chip clears, Create re-enables.
    await user.clear(screen.getByLabelText('Quantity for line 1'));
    await user.type(screen.getByLabelText('Quantity for line 1'), '3');
    expect(await screen.findByText(/in stock/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create order' })).toBeEnabled();
  });

  it('creates the order and toasts success', async () => {
    let body: unknown;
    server.use(
      ...baseHandlers(),
      http.post(`${BASE}/sales-orders`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: 'so-new', so_number: 'SO-202606-000001' }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<SalesOrderCreatePage />);

    await screen.findByRole('option', { name: 'Acme' });
    await user.selectOptions(screen.getByLabelText('Customer'), 'c1');
    await user.selectOptions(screen.getByLabelText('Item for line 1'), 'i1');
    await user.type(screen.getByLabelText('Quantity for line 1'), '3');
    await user.click(screen.getByRole('button', { name: 'Create order' }));

    expect(await screen.findByText('SO-202606-000001 created.')).toBeInTheDocument();
    expect(body).toMatchObject({ customer_id: 'c1', items: [{ item_id: 'i1', quantity: '3' }] });
  });
});
