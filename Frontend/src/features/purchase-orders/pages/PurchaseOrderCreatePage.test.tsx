import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { PurchaseOrderCreatePage } from './PurchaseOrderCreatePage';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const VENDORS = [{ id: 'v1', vendor_name: 'Steelcraft Co.', is_active: true }];
const ITEMS = [
  { id: 'i1', sku: 'RAW-1', name: 'Raw Steel', type: 'RAW', unit_of_measure: 'kg', stock_quantity: '0', reorder_threshold: null, unit_price: '5', status: 'NO_STOCK' },
];

function baseHandlers() {
  return [
    http.get(`${BASE}/vendors`, () => HttpResponse.json({ items: VENDORS, total: 1, limit: 100, offset: 0 })),
    http.get(`${BASE}/items`, () => HttpResponse.json({ items: ITEMS, total: 1, limit: 100, offset: 0 })),
  ];
}

describe('PurchaseOrderCreatePage', () => {
  it('validates vendor and line items before submit', async () => {
    server.use(...baseHandlers());
    const user = userEvent.setup();
    renderWithProviders(<PurchaseOrderCreatePage />);

    await screen.findByLabelText('Item for line 1');
    await user.click(screen.getByRole('button', { name: 'Save as Draft' }));

    expect(await screen.findByText('Pick a vendor')).toBeInTheDocument();
    expect(screen.getByText('Pick an item')).toBeInTheDocument();
    expect(screen.getByText('Qty required')).toBeInTheDocument();
  });

  it('creates a draft PO and toasts success', async () => {
    let body: unknown;
    server.use(
      ...baseHandlers(),
      http.post(`${BASE}/purchase-orders`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: 'po-new', po_number: 'PO-202606-000001' }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<PurchaseOrderCreatePage />);

    await screen.findByRole('option', { name: 'Steelcraft Co.' });
    await user.selectOptions(screen.getByLabelText('Vendor'), 'v1');
    await user.selectOptions(screen.getByLabelText('Item for line 1'), 'i1');
    await user.type(screen.getByLabelText('Quantity for line 1'), '100');
    await user.click(screen.getByRole('button', { name: 'Save as Draft' }));

    expect(await screen.findByText('PO-202606-000001 created.')).toBeInTheDocument();
    expect(body).toMatchObject({ vendor_id: 'v1', items: [{ item_id: 'i1', quantity: '100' }] });
  });

  it('surfaces PRICE_UNAVAILABLE as a danger toast with the Request ID', async () => {
    server.use(
      ...baseHandlers(),
      http.post(`${BASE}/purchase-orders`, () =>
        HttpResponse.json(
          { error: { code: 'PRICE_UNAVAILABLE', message: 'No price for this item', request_id: 'req-pu' } },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<PurchaseOrderCreatePage />);

    await screen.findByRole('option', { name: 'Steelcraft Co.' });
    await user.selectOptions(screen.getByLabelText('Vendor'), 'v1');
    await user.selectOptions(screen.getByLabelText('Item for line 1'), 'i1');
    await user.type(screen.getByLabelText('Quantity for line 1'), '100');
    await user.click(screen.getByRole('button', { name: 'Save as Draft' }));

    const toast = (await screen.findByText('No price for this item')).closest('.toast');
    expect(toast).toHaveClass('danger');
    expect(toast).toHaveTextContent('Request ID: req-pu');
  });
});
