import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { NeedsAttention } from './NeedsAttention';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function itemsResponse(items: unknown[]) {
  return HttpResponse.json({ items, total: items.length, limit: 100, offset: 0 });
}

describe('NeedsAttention', () => {
  it('lists low-stock items with their ratio', async () => {
    server.use(
      http.get(`${BASE}/items`, () =>
        itemsResponse([
          {
            id: 'i1',
            sku: 'ITM-2',
            name: 'Raw Steel',
            type: 'RAW',
            unit_of_measure: 'kg',
            stock_quantity: '40',
            reorder_threshold: '100',
            unit_price: '5',
            status: 'LOW_STOCK',
          },
          {
            id: 'i2',
            sku: 'OK-1',
            name: 'Healthy',
            type: 'RAW',
            unit_of_measure: 'kg',
            stock_quantity: '900',
            reorder_threshold: '100',
            unit_price: '5',
            status: 'IN_STOCK',
          },
        ]),
      ),
    );

    renderWithProviders(<NeedsAttention />);

    expect(await screen.findByText('Raw Steel')).toBeInTheDocument();
    expect(screen.getByText('ITM-2 · Raw Material')).toBeInTheDocument();
    expect(screen.getByText('40 / 100 kg')).toBeInTheDocument();
    // The in-stock item is not listed.
    expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
  });

  it('shows an all-clear empty state when nothing is low', async () => {
    server.use(
      http.get(`${BASE}/items`, () =>
        itemsResponse([
          {
            id: 'i2',
            sku: 'OK-1',
            name: 'Healthy',
            type: 'RAW',
            unit_of_measure: 'kg',
            stock_quantity: '900',
            reorder_threshold: '100',
            unit_price: '5',
            status: 'IN_STOCK',
          },
        ]),
      ),
    );

    renderWithProviders(<NeedsAttention />);
    expect(await screen.findByText('All stocked up')).toBeInTheDocument();
  });

  it('shows an error with the Request ID on failure', async () => {
    server.use(
      http.get(`${BASE}/items`, () =>
        HttpResponse.json(
          { error: { code: 'UNKNOWN_ERROR', message: 'Boom', request_id: 'req-low' } },
          { status: 500 },
        ),
      ),
    );

    renderWithProviders(<NeedsAttention />);
    expect(await screen.findByText("Couldn't load low-stock items")).toBeInTheDocument();
    expect(screen.getByText(/Request ID: req-low/)).toBeInTheDocument();
  });
});
