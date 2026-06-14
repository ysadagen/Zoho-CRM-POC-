import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
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

const VENDOR = {
  id: 'v1',
  vendor_name: 'Steelcraft Co.',
  contact_person: 'Ravi',
  email: 'sales@steelcraft.test',
  phone: '123',
  vendor_code: 'STL-1',
  gstin: 'GST9',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-05-01T00:00:00Z',
};

const TERMS = [
  {
    id: 't1',
    vendor_id: 'v1',
    item_id: 'i1',
    rate: '150.00',
    discount_percent: '5.00',
    effective_from: '2026-01-01',
    effective_to: null,
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

const POS = [
  {
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
    items: [],
    created_at: '2026-05-10T00:00:00Z',
    updated_at: '2026-05-10T00:00:00Z',
  },
];

function handlers() {
  return [
    http.get(`${BASE}/vendors/v1`, () => HttpResponse.json(VENDOR)),
    http.get(`${BASE}/vendors/v1/terms`, () =>
      HttpResponse.json({ items: TERMS, total: 1, limit: 100, offset: 0 }),
    ),
    http.get(`${BASE}/purchase-orders`, () =>
      HttpResponse.json({ items: POS, total: 1, limit: 50, offset: 0 }),
    ),
    http.get(`${BASE}/items`, () =>
      HttpResponse.json({
        items: [{ id: 'i1', sku: 'RAW-1', name: 'Raw Steel', unit_of_measure: 'kg' }],
        total: 1,
        limit: 100,
        offset: 0,
      }),
    ),
  ];
}

describe('VendorDetailPage', () => {
  it('shows the profile by default', async () => {
    server.use(...handlers());
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/vendors/v1' });
    expect(await screen.findByRole('heading', { name: 'Steelcraft Co.' })).toBeInTheDocument();
    expect(screen.getByText('sales@steelcraft.test')).toBeInTheDocument();
  });

  it('shows linked terms on the Items supplied tab', async () => {
    server.use(...handlers());
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/vendors/v1' });
    await screen.findByRole('heading', { name: 'Steelcraft Co.' });

    await user.click(screen.getByRole('tab', { name: 'Items supplied' }));
    expect(await screen.findByText('RAW-1 — Raw Steel')).toBeInTheDocument();
  });

  it('shows purchase orders on the Purchase orders tab', async () => {
    server.use(...handlers());
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/vendors/v1' });
    await screen.findByRole('heading', { name: 'Steelcraft Co.' });

    await user.click(screen.getByRole('tab', { name: 'Purchase orders' }));
    expect(await screen.findByText('PO-202605-000001')).toBeInTheDocument();
  });

  it('shows a page error with the Request ID when the vendor fails to load', async () => {
    server.use(
      http.get(`${BASE}/vendors/v1`, () =>
        HttpResponse.json(
          { error: { code: 'VENDOR_NOT_FOUND', message: 'Not found', request_id: 'req-v404' } },
          { status: 404 },
        ),
      ),
      http.get(`${BASE}/vendors/v1/terms`, () =>
        HttpResponse.json({ items: [], total: 0, limit: 100, offset: 0 }),
      ),
      http.get(`${BASE}/purchase-orders`, () =>
        HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 }),
      ),
    );
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/vendors/v1' });
    await waitFor(() => expect(screen.getByText(/Request ID: req-v404/)).toBeInTheDocument());
  });
});
