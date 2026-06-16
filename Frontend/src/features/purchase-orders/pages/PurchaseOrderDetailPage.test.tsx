import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
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

const VENDORS = [{ id: 'v1', vendor_name: 'Steelcraft Co.', is_active: true }];
const ITEMS = [{ id: 'i1', sku: 'RAW-1', name: 'Raw Steel', unit_of_measure: 'kg' }];
const PO_DRAFT = {
  id: 'po1',
  po_number: 'PO-202605-000001',
  vendor_id: 'v1',
  order_date: '2026-05-10',
  expected_delivery_date: '2026-05-20',
  received_date: null,
  status: 'DRAFT',
  subtotal: '500',
  total: '500',
  notes: 'Initial stock-up',
  items: [{ id: 'l1', purchase_order_id: 'po1', item_id: 'i1', quantity: '100', unit_price: '5', line_total: '500', created_at: '' }],
  created_at: '2026-05-10T00:00:00Z',
  updated_at: '2026-05-10T00:00:00Z',
};

function commonHandlers() {
  return [
    http.get(`${BASE}/vendors`, () => HttpResponse.json({ items: VENDORS, total: 1, limit: 100, offset: 0 })),
    http.get(`${BASE}/items`, () => HttpResponse.json({ items: ITEMS, total: 1, limit: 100, offset: 0 })),
  ];
}

describe('PurchaseOrderDetailPage', () => {
  it('shows the PO header and line items', async () => {
    server.use(...commonHandlers(), http.get(`${BASE}/purchase-orders/po1`, () => HttpResponse.json(PO_DRAFT)));
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/purchase-orders/po1' });

    expect(await screen.findByText('PO-202605-000001')).toBeInTheDocument();
    expect(await screen.findByText('Raw Steel')).toBeInTheDocument();
    expect(screen.getByText('Initial stock-up')).toBeInTheDocument();
  });

  it('receives the PO through the confirmation modal', async () => {
    let received = false;
    server.use(
      ...commonHandlers(),
      http.get(`${BASE}/purchase-orders/po1`, () => HttpResponse.json(PO_DRAFT)),
      http.post(`${BASE}/purchase-orders/po1/receive`, () => {
        received = true;
        return HttpResponse.json({ ...PO_DRAFT, status: 'RECEIVED', received_date: '2026-05-12' });
      }),
    );
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/purchase-orders/po1' });
    await screen.findByText('PO-202605-000001');

    await user.click(screen.getByRole('button', { name: 'Receive' }));
    const dialog = await screen.findByRole('dialog', { name: 'Receive PO-202605-000001' });
    // Lot details are required to receive (pharma stock enters with an expiry).
    await user.type(within(dialog).getByLabelText(/Batch number/), 'LOT-A');
    fireEvent.change(within(dialog).getByLabelText(/Expiry date/), {
      target: { value: '2030-01-01' },
    });
    await user.click(within(dialog).getByRole('button', { name: 'Confirm receive' }));

    await waitFor(() => expect(received).toBe(true));
    expect(await screen.findByText('Stock received — lots created.')).toBeInTheDocument();
  });

  it('splits a line across multiple lots and posts each lot (#10)', async () => {
    let body: { lines: Array<Record<string, string>> } | undefined;
    server.use(
      ...commonHandlers(),
      http.get(`${BASE}/purchase-orders/po1`, () => HttpResponse.json(PO_DRAFT)),
      http.post(`${BASE}/purchase-orders/po1/receive`, async ({ request }) => {
        body = (await request.json()) as typeof body;
        return HttpResponse.json({ ...PO_DRAFT, status: 'RECEIVED', received_date: '2026-05-12' });
      }),
    );
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/purchase-orders/po1' });
    await screen.findByText('PO-202605-000001');

    await user.click(screen.getByRole('button', { name: 'Receive' }));
    const dialog = await screen.findByRole('dialog', { name: 'Receive PO-202605-000001' });

    // Lot 1 (qty seeded to the full 100) — name it and cut it to 60.
    await user.type(within(dialog).getByLabelText('Batch number'), 'LOT-A');
    fireEvent.change(within(dialog).getByLabelText('Expiry date'), { target: { value: '2030-01-01' } });
    const qty1 = within(dialog).getByLabelText('Quantity');
    await user.clear(qty1);
    await user.type(qty1, '60');

    // Add a second lot → allocation is short (60/100), Confirm disabled.
    await user.click(within(dialog).getByRole('button', { name: 'Add lot' }));
    expect(within(dialog).getByText('Allocated 60 / 100')).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Confirm receive' })).toBeDisabled();

    // Fill lot 2 with the remaining 40 → allocation balances, Confirm enables.
    const [, batch2] = within(dialog).getAllByLabelText('Batch number');
    const [, expiry2] = within(dialog).getAllByLabelText('Expiry date');
    const [, qty2] = within(dialog).getAllByLabelText('Quantity');
    await user.type(batch2!, 'LOT-B');
    fireEvent.change(expiry2!, { target: { value: '2031-06-01' } });
    await user.type(qty2!, '40');

    expect(within(dialog).getByText('Allocated 100 / 100')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Confirm receive' }));

    await waitFor(() => expect(body).toBeTruthy());
    expect(body?.lines).toEqual([
      expect.objectContaining({ item_id: 'i1', batch_number: 'LOT-A', quantity: '60' }),
      expect.objectContaining({ item_id: 'i1', batch_number: 'LOT-B', quantity: '40' }),
    ]);
  });

  it('shows a page error with the Request ID when the PO fails to load', async () => {
    server.use(
      ...commonHandlers(),
      http.get(`${BASE}/purchase-orders/po1`, () =>
        HttpResponse.json(
          { error: { code: 'PURCHASE_ORDER_NOT_FOUND', message: 'Not found', request_id: 'req-po404' } },
          { status: 404 },
        ),
      ),
    );
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/purchase-orders/po1' });
    await waitFor(() => expect(screen.getByText(/Request ID: req-po404/)).toBeInTheDocument());
  });
});
