import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { StockMovementsListPage } from './StockMovementsListPage';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const MOVEMENTS = [
  {
    id: 'm1',
    item_id: 'i1',
    direction: 'IN',
    reason: 'PURCHASE',
    quantity: '100',
    signed_quantity: '100',
    stock_before: '0',
    stock_after: '100',
    reference_type: 'PURCHASE_ORDER',
    reference_id: 'po1',
    batch_id: 'b1',
    remarks: null,
    created_by_user_id: 'u1',
    created_at: '2026-05-01T10:00:00Z',
  },
];

function handlers(onUrl?: (url: URL) => void) {
  return [
    http.get(`${BASE}/items`, () =>
      HttpResponse.json({ items: [{ id: 'i1', sku: 'RAW-1', name: 'Raw Steel', unit_of_measure: 'kg' }], total: 1, limit: 100, offset: 0 }),
    ),
    // Party resolution joins PO→vendor / SO→customer client-side.
    http.get(`${BASE}/purchase-orders`, () =>
      HttpResponse.json({ items: [{ id: 'po1', vendor_id: 'v1' }], total: 1, limit: 100, offset: 0 }),
    ),
    http.get(`${BASE}/sales-orders`, () =>
      HttpResponse.json({ items: [], total: 0, limit: 100, offset: 0 }),
    ),
    http.get(`${BASE}/vendors`, () =>
      HttpResponse.json({ items: [{ id: 'v1', vendor_name: 'Acme Steel Co' }], total: 1, limit: 100, offset: 0 }),
    ),
    http.get(`${BASE}/customers`, () =>
      HttpResponse.json({ items: [], total: 0, limit: 100, offset: 0 }),
    ),
    // Lot resolution joins movement.batch_id → batch number client-side.
    http.get(`${BASE}/batches`, () =>
      HttpResponse.json(
        { items: [{ id: 'b1', item_id: 'i1', batch_number: 'LOT-7' }], total: 1, limit: 100, offset: 0 },
      ),
    ),
    http.get(`${BASE}/stock-movements`, ({ request }) => {
      onUrl?.(new URL(request.url));
      return HttpResponse.json({ items: MOVEMENTS, total: 1, limit: 25, offset: 0 });
    }),
  ];
}

describe('StockMovementsListPage', () => {
  it('renders the ledger with item name and a linked reference', async () => {
    server.use(...handlers());
    renderWithProviders(<StockMovementsListPage />);

    expect(await screen.findByText('Raw Steel')).toBeInTheDocument();
    expect(screen.getByText('IN ↑')).toBeInTheDocument();
    const ref = screen.getByRole('link', { name: 'Purchase order' });
    expect(ref).toHaveAttribute('href', '/purchase-orders/po1');
  });

  it('resolves the customer/vendor for a movement', async () => {
    server.use(...handlers());
    renderWithProviders(<StockMovementsListPage />);

    expect(await screen.findByText('Acme Steel Co')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Customer / Vendor' })).toBeInTheDocument();
  });

  it('shows the lot (batch number) a movement touched', async () => {
    server.use(...handlers());
    renderWithProviders(<StockMovementsListPage />);

    expect(await screen.findByText('LOT-7')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Lot' })).toBeInTheDocument();
  });

  it('is read-only — no edit or delete controls', async () => {
    server.use(...handlers());
    renderWithProviders(<StockMovementsListPage />);
    await screen.findByText('Raw Steel');

    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument();
  });

  it('sends the direction filter to the server', async () => {
    const urls: URL[] = [];
    server.use(...handlers((url) => urls.push(url)));
    const user = userEvent.setup();
    renderWithProviders(<StockMovementsListPage />);
    await screen.findByText('Raw Steel');

    await user.click(screen.getByRole('tab', { name: 'OUT' }));
    await waitFor(() => expect(urls.at(-1)?.searchParams.get('direction')).toBe('OUT'));
  });

  it('opens the manual-adjustment modal', async () => {
    server.use(...handlers());
    const user = userEvent.setup();
    renderWithProviders(<StockMovementsListPage />);
    await screen.findByText('Raw Steel');

    await user.click(screen.getByRole('button', { name: 'Manual Adjustment' }));
    expect(await screen.findByRole('dialog', { name: 'Manual Adjustment' })).toBeInTheDocument();
  });
});
