import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { PurchaseOrdersListPage } from './PurchaseOrdersListPage';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const VENDORS = [{ id: 'v1', vendor_name: 'Steelcraft Co.', is_active: true }];
const PO = {
  id: 'po1',
  po_number: 'PO-202605-000001',
  vendor_id: 'v1',
  order_date: '2026-05-10',
  expected_delivery_date: null,
  received_date: null,
  status: 'DRAFT',
  subtotal: '500',
  total: '500',
  notes: null,
  items: [{ id: 'l1', purchase_order_id: 'po1', item_id: 'i1', quantity: '100', unit_price: '5', line_total: '500', created_at: '' }],
  created_at: '2026-05-10T00:00:00Z',
  updated_at: '2026-05-10T00:00:00Z',
};

function handlers(onPoUrl?: (url: URL) => void) {
  return [
    http.get(`${BASE}/vendors`, () => HttpResponse.json({ items: VENDORS, total: 1, limit: 100, offset: 0 })),
    http.get(`${BASE}/purchase-orders`, ({ request }) => {
      onPoUrl?.(new URL(request.url));
      return HttpResponse.json({ items: [PO], total: 1, limit: 25, offset: 0 });
    }),
    http.get(`${BASE}/items`, () =>
      HttpResponse.json({ items: [{ id: 'i1', sku: 'RAW-1', name: 'Raw Steel', unit_of_measure: 'kg' }], total: 1, limit: 100, offset: 0 }),
    ),
  ];
}

describe('PurchaseOrdersListPage', () => {
  it('lists POs with the resolved vendor name', async () => {
    server.use(...handlers());
    renderWithProviders(<PurchaseOrdersListPage />);
    expect(await screen.findByText('PO-202605-000001')).toBeInTheDocument();
    // Vendor name appears in both the filter dropdown and the row cell.
    expect((await screen.findAllByText('Steelcraft Co.')).length).toBeGreaterThan(0);
  });

  it('sends the status filter to the server', async () => {
    const urls: URL[] = [];
    server.use(...handlers((url) => urls.push(url)));
    const user = userEvent.setup();
    renderWithProviders(<PurchaseOrdersListPage />);
    await screen.findByText('PO-202605-000001');

    await user.click(screen.getByRole('tab', { name: 'Received' }));
    await waitFor(() => expect(urls.at(-1)?.searchParams.get('status')).toBe('RECEIVED'));
  });

  it('opens the receive confirmation from an inline Receive', async () => {
    server.use(...handlers());
    const user = userEvent.setup();
    renderWithProviders(<PurchaseOrdersListPage />);
    await screen.findByText('PO-202605-000001');

    await user.click(screen.getByRole('button', { name: 'Receive' }));
    expect(await screen.findByRole('dialog', { name: 'Receive PO-202605-000001' })).toBeInTheDocument();
    // The receive modal now collects per-line lot details.
    expect(await screen.findByLabelText(/Batch number/)).toBeInTheDocument();
  });
});
