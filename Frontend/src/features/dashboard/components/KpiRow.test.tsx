import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { KpiRow } from './KpiRow';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function okHandlers() {
  return [
    http.get(`${BASE}/items`, () =>
      HttpResponse.json({
        items: [
          {
            id: 'i1',
            sku: 'A',
            name: 'A',
            type: 'RAW',
            unit_of_measure: 'kg',
            stock_quantity: '10',
            reorder_threshold: '5',
            unit_price: '4',
            status: 'IN_STOCK',
          },
          {
            id: 'i2',
            sku: 'B',
            name: 'B',
            type: 'FINISHED',
            unit_of_measure: 'pcs',
            stock_quantity: '2',
            reorder_threshold: '50',
            unit_price: '1',
            status: 'LOW_STOCK',
          },
        ],
        total: 2,
        limit: 100,
        offset: 0,
      }),
    ),
    http.get(`${BASE}/purchase-orders`, () =>
      HttpResponse.json({ items: [], total: 3, limit: 1, offset: 0 }),
    ),
    http.get(`${BASE}/sales-orders`, () =>
      HttpResponse.json({ items: [], total: 2, limit: 1, offset: 0 }),
    ),
  ];
}

describe('KpiRow', () => {
  it('shows skeletons while loading, then live KPI values', async () => {
    server.use(...okHandlers());
    const { container } = renderWithProviders(<KpiRow />);

    // Pending on first paint → shimmer placeholders, no values yet.
    expect(container.querySelectorAll('.skeleton').length).toBeGreaterThan(0);

    expect(await screen.findByText('Total Stock Value')).toBeInTheDocument();
    expect(screen.getByText('Low Stock Items')).toBeInTheDocument();
    expect(screen.getByText('Open Purchase Orders')).toBeInTheDocument();
    expect(screen.getByText('Open Sales Orders')).toBeInTheDocument();
    // 1 low-stock item, 3 draft POs, 2 draft SOs.
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    // CRM sync is an honest placeholder (no Integration Layer yet).
    expect(screen.getByText('CRM Sync Health')).toBeInTheDocument();
    expect(screen.getByText('Awaiting Integration Layer')).toBeInTheDocument();
  });

  it('renders an error with the Request ID and retries', async () => {
    let calls = 0;
    server.use(
      http.get(`${BASE}/items`, () => {
        calls += 1;
        if (calls === 1) {
          return HttpResponse.json(
            { error: { code: 'UNKNOWN_ERROR', message: 'Boom', request_id: 'req-123' } },
            { status: 500 },
          );
        }
        return HttpResponse.json({ items: [], total: 0, limit: 100, offset: 0 });
      }),
      http.get(`${BASE}/purchase-orders`, () =>
        HttpResponse.json({ items: [], total: 0, limit: 1, offset: 0 }),
      ),
      http.get(`${BASE}/sales-orders`, () =>
        HttpResponse.json({ items: [], total: 0, limit: 1, offset: 0 }),
      ),
    );

    renderWithProviders(<KpiRow />);

    expect(await screen.findByText("Couldn't load the summary")).toBeInTheDocument();
    expect(screen.getByText(/Request ID: req-123/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /retry/i }));

    // Second fetch succeeds → KPIs render.
    expect(await screen.findByText('Total Stock Value')).toBeInTheDocument();
  });
});
