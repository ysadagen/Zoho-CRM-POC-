import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { BatchesListPage } from './BatchesListPage';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const BATCHES = [
  {
    id: 'b1',
    item_id: 'i1',
    batch_number: 'LOT-A',
    batch_status: 'RELEASED',
    batch_received_date: null,
    manufacturing_date: null,
    expiry_date: '2030-01-01',
    quantity: '40',
    initial_quantity: '40',
    unit_cost: '12.50',
    storage_location: 'Cold Room A',
    vendor_id: null,
    received_via_po_id: null,
    is_expired: false,
    created_by_user_id: 'u1',
    updated_by_user_id: 'u1',
    created_at: '2026-05-01T10:00:00Z',
    updated_at: '2026-05-01T10:00:00Z',
  },
];

function handlers(onUrl?: (url: URL) => void, batches: unknown[] = BATCHES) {
  return [
    http.get(`${BASE}/items`, () =>
      HttpResponse.json(
        { items: [{ id: 'i1', sku: 'RAW-1', name: 'Raw Steel', unit_of_measure: 'kg' }], total: 1, limit: 100, offset: 0 },
      ),
    ),
    http.get(`${BASE}/batches`, ({ request }) => {
      onUrl?.(new URL(request.url));
      return HttpResponse.json({ items: batches, total: batches.length, limit: 25, offset: 0 });
    }),
  ];
}

describe('BatchesListPage', () => {
  it('renders lots with the item name, number and status', async () => {
    server.use(...handlers());
    renderWithProviders(<BatchesListPage />);

    expect(await screen.findByText('Raw Steel')).toBeInTheDocument();
    expect(screen.getByText('LOT-A')).toBeInTheDocument();
    // Location cell combines location + unit cost into one node.
    expect(screen.getByText(/Cold Room A/)).toBeInTheDocument();
    // "Released" appears both as the row badge and the filter option — assert
    // at least the badge is present.
    expect(screen.getAllByText('Released').length).toBeGreaterThanOrEqual(1);
  });

  it('recalls a released lot through the QC action (#7)', async () => {
    let body: { status?: string } | undefined;
    server.use(
      ...handlers(),
      http.post(`${BASE}/batches/b1/status`, async ({ request }) => {
        body = (await request.json()) as typeof body;
        return HttpResponse.json({ ...BATCHES[0], batch_status: 'RECALLED' });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<BatchesListPage />);
    await screen.findByText('LOT-A');

    // A RELEASED lot offers a single "Recall" QC action.
    await user.click(screen.getByRole('button', { name: 'Recall' }));
    await waitFor(() => expect(body?.status).toBe('RECALLED'));
    expect(await screen.findByText('Lot LOT-A recalled.')).toBeInTheDocument();
  });

  it('forwards the status filter to the server', async () => {
    const urls: URL[] = [];
    server.use(...handlers((url) => urls.push(url)));
    const user = userEvent.setup();
    renderWithProviders(<BatchesListPage />);
    await screen.findByText('Raw Steel');

    await user.selectOptions(screen.getByLabelText('Filter by status'), 'RELEASED');
    await waitFor(() => expect(urls.at(-1)?.searchParams.get('status')).toBe('RELEASED'));
  });

  it('shows an empty state when there are no lots', async () => {
    server.use(...handlers(undefined, []));
    renderWithProviders(<BatchesListPage />);

    expect(await screen.findByText('No lots yet')).toBeInTheDocument();
  });

  it('opens the record-lot drawer', async () => {
    server.use(...handlers());
    const user = userEvent.setup();
    renderWithProviders(<BatchesListPage />);
    await screen.findByText('Raw Steel');

    await user.click(screen.getByRole('button', { name: 'New Lot' }));
    expect(await screen.findByRole('dialog', { name: 'Record Lot' })).toBeInTheDocument();
  });
});
