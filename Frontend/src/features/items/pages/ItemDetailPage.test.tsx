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

const ITEM = {
  id: 'i1',
  sku: 'RAW-1',
  name: 'Raw Steel',
  description: 'Sheets',
  type: 'RAW',
  category: null,
  unit_of_measure: 'kg',
  stock_quantity: '40',
  reorder_threshold: '100',
  unit_price: '5',
  status: 'LOW_STOCK',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-05-01T00:00:00Z',
};

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
    remarks: null,
    created_by_user_id: 'u1',
    created_at: '2026-05-01T10:00:00Z',
  },
];

function handlers() {
  return [
    http.get(`${BASE}/items/i1`, () => HttpResponse.json(ITEM)),
    http.get(`${BASE}/stock-movements`, () =>
      HttpResponse.json({ items: MOVEMENTS, total: 1, limit: 50, offset: 0 }),
    ),
  ];
}

describe('ItemDetailPage', () => {
  it('shows the item header, stat cards and overview', async () => {
    server.use(...handlers());
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/items/i1' });

    expect(await screen.findByRole('heading', { name: 'Raw Steel' })).toBeInTheDocument();
    // Stat cards (labels unique to the stat row) are derived from the movements.
    expect(screen.getByText('Total inbound')).toBeInTheDocument();
    expect(screen.getByText('Total outbound')).toBeInTheDocument();
    // Overview master field (unique to the overview grid).
    expect(screen.getByText('Default unit price')).toBeInTheDocument();
  });

  it('switches to the movement-history tab', async () => {
    server.use(...handlers());
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/items/i1' });
    await screen.findByRole('heading', { name: 'Raw Steel' });

    await user.click(screen.getByRole('tab', { name: 'Movement history' }));
    expect(await screen.findByText('Balance after')).toBeInTheDocument();
    expect(screen.getByText('Purchase order')).toBeInTheDocument();
  });

  it('opens the edit drawer prefilled', async () => {
    server.use(...handlers());
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/items/i1' });
    await screen.findByRole('heading', { name: 'Raw Steel' });

    await user.click(screen.getByRole('button', { name: 'Edit' }));
    const dialog = await screen.findByRole('dialog', { name: 'Edit Item' });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByLabelText('Name')).toHaveValue('Raw Steel');
  });

  it('shows a page error when the item fails to load', async () => {
    server.use(
      http.get(`${BASE}/items/i1`, () =>
        HttpResponse.json(
          { error: { code: 'ITEM_NOT_FOUND', message: 'Item not found', request_id: 'req-404' } },
          { status: 404 },
        ),
      ),
      http.get(`${BASE}/stock-movements`, () =>
        HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 }),
      ),
    );
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/items/i1' });

    await waitFor(() =>
      expect(screen.getByText(/Request ID: req-404/)).toBeInTheDocument(),
    );
  });
});
