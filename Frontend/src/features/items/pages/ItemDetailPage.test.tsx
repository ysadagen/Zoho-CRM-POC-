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
  storage_condition: 'COLD_CHAIN_2_8',
  shelf_life_days: 365,
  raw_detail: { material_classification: 'API', pharmacopoeia: 'IP', is_hazardous: true },
  finished_detail: null,
  status: 'LOW_STOCK',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-05-01T00:00:00Z',
};

const FINISHED_ITEM = {
  id: 'f1',
  sku: 'PCM-500',
  name: 'Paracetamol 500',
  description: null,
  type: 'FINISHED',
  category: 'Analgesic',
  unit_of_measure: 'strip',
  stock_quantity: '200',
  reorder_threshold: '50',
  unit_price: '20',
  storage_condition: 'AMBIENT',
  shelf_life_days: 730,
  raw_detail: null,
  finished_detail: {
    generic_name: 'Paracetamol',
    brand_name: 'Calpol',
    strength: '500 mg',
    dosage_form: 'TABLET',
    pack_size: '10x10',
    ingredients: 'Paracetamol IP 500mg',
    container_specification: 'Blister',
    selling_price: '18.00',
    license_number: 'LIC-1',
    registration_code: 'REG-1',
    mrp: '25.00',
    drug_schedule: 'H',
    is_prescription_required: true,
  },
  status: 'IN_STOCK',
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
    // Pharma: common fields + the RAW detail block render with human labels.
    expect(screen.getByText('Raw material details')).toBeInTheDocument();
    expect(screen.getByText('Active (API)')).toBeInTheDocument();
    expect(screen.getByText('Cold chain (2–8°C)')).toBeInTheDocument();
  });

  it('deactivates the item through the confirm modal (#1)', async () => {
    let deleted = false;
    server.use(
      ...handlers(),
      http.delete(`${BASE}/items/i1`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
      http.get(`${BASE}/items`, () =>
        HttpResponse.json({ items: [], total: 0, limit: 25, offset: 0 }),
      ),
    );
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/items/i1' });

    await screen.findByRole('heading', { name: 'Raw Steel' });
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    const dialog = await screen.findByRole('dialog', { name: 'Deactivate Raw Steel?' });
    await user.click(within(dialog).getByRole('button', { name: 'Deactivate' }));

    await waitFor(() => expect(deleted).toBe(true));
    expect(await screen.findByText('Raw Steel deactivated.')).toBeInTheDocument();
  });

  it('reactivates a deactivated item from the detail screen', async () => {
    let patchBody: unknown;
    server.use(
      http.get(`${BASE}/items/i1`, () => HttpResponse.json({ ...ITEM, is_active: false })),
      http.get(`${BASE}/stock-movements`, () =>
        HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 }),
      ),
      http.patch(`${BASE}/items/i1`, async ({ request }) => {
        patchBody = await request.json();
        return HttpResponse.json({ ...ITEM, is_active: true });
      }),
    );
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/items/i1' });

    await screen.findByRole('heading', { name: 'Raw Steel' });
    // An inactive item shows Reactivate, not Deactivate.
    expect(screen.queryByRole('button', { name: 'Deactivate' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reactivate' }));

    await waitFor(() => expect(patchBody).toEqual({ is_active: true }));
    expect(await screen.findByText('Raw Steel reactivated.')).toBeInTheDocument();
  });

  it('renders the finished-product detail block with human labels', async () => {
    server.use(
      http.get(`${BASE}/items/f1`, () => HttpResponse.json(FINISHED_ITEM)),
      http.get(`${BASE}/stock-movements`, () =>
        HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 }),
      ),
    );
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/items/f1' });

    expect(await screen.findByRole('heading', { name: 'Paracetamol 500' })).toBeInTheDocument();
    expect(screen.getByText('Finished product details')).toBeInTheDocument();
    expect(screen.getByText('Tablet')).toBeInTheDocument();
    expect(screen.getByText('Schedule H')).toBeInTheDocument();
    expect(screen.getByText('Required')).toBeInTheDocument();
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

  it('defaults the back link to the Items list', async () => {
    server.use(...handlers());
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/items/i1' });
    await screen.findByRole('heading', { name: 'Raw Steel' });

    expect(screen.getByRole('link', { name: '← Items' })).toHaveAttribute('href', '/items');
  });

  it('returns to the originating page when navigated with Link state', async () => {
    server.use(...handlers());
    seedSession();
    renderWithProviders(<AppRouter />, {
      route: '/items/i1',
      state: { from: '/stock-movements', fromLabel: 'Stock Movements' },
    });
    await screen.findByRole('heading', { name: 'Raw Steel' });

    expect(screen.getByRole('link', { name: '← Stock Movements' })).toHaveAttribute(
      'href',
      '/stock-movements',
    );
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
