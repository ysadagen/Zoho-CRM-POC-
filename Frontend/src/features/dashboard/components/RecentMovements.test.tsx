import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { RecentMovements } from './RecentMovements';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const ITEMS_OK = http.get(`${BASE}/items`, () =>
  HttpResponse.json({
    items: [{ id: 'i1', name: 'Bottle 1L', unit_of_measure: 'pcs' }],
    total: 1,
    limit: 100,
    offset: 0,
  }),
);

describe('RecentMovements', () => {
  it('renders live movements with resolved item name, signed qty and reference', async () => {
    server.use(
      ITEMS_OK,
      http.get(`${BASE}/stock-movements`, () =>
        HttpResponse.json({
          items: [
            {
              id: 'm1',
              item_id: 'i1',
              direction: 'OUT',
              reason: 'SALE',
              quantity: '120',
              signed_quantity: '-120',
              stock_before: '200',
              stock_after: '80',
              reference_type: 'SALES_ORDER',
              reference_id: 'so1',
              remarks: null,
              created_by_user_id: 'u1',
              created_at: '2026-05-28T14:32:00Z',
            },
          ],
          total: 1,
          limit: 5,
          offset: 0,
        }),
      ),
    );

    renderWithProviders(<RecentMovements />);

    expect(await screen.findByText('Bottle 1L')).toBeInTheDocument();
    // The item name links through to its detail page.
    expect(screen.getByRole('link', { name: 'Bottle 1L' })).toHaveAttribute('href', '/items/i1');
    expect(screen.getByText('Sale Out')).toBeInTheDocument();
    expect(screen.getByText(/120 pcs/)).toBeInTheDocument();
    expect(screen.getByText('Sales order')).toBeInTheDocument();
    // All columns are centre-aligned on the dashboard (see dashboard.css).
    expect(screen.getByRole('table')).toHaveClass('tbl-center');
  });

  it('shows an empty state when there are no movements', async () => {
    server.use(
      ITEMS_OK,
      http.get(`${BASE}/stock-movements`, () =>
        HttpResponse.json({ items: [], total: 0, limit: 5, offset: 0 }),
      ),
    );

    renderWithProviders(<RecentMovements />);
    expect(await screen.findByText('No movements yet')).toBeInTheDocument();
  });

  it('shows an error with the Request ID on failure', async () => {
    server.use(
      ITEMS_OK,
      http.get(`${BASE}/stock-movements`, () =>
        HttpResponse.json(
          { error: { code: 'UNKNOWN_ERROR', message: 'Boom', request_id: 'req-mv' } },
          { status: 500 },
        ),
      ),
    );

    renderWithProviders(<RecentMovements />);
    expect(await screen.findByText("Couldn't load movements")).toBeInTheDocument();
    expect(screen.getByText(/Request ID: req-mv/)).toBeInTheDocument();
  });
});
