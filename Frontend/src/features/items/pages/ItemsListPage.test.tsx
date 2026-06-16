import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { ItemsListPage } from './ItemsListPage';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const ITEMS = [
  {
    id: 'i1',
    sku: 'RAW-1',
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
    sku: 'FIN-1',
    name: 'Bottle 1L',
    type: 'FINISHED',
    unit_of_measure: 'pcs',
    stock_quantity: '900',
    reorder_threshold: '100',
    unit_price: '45',
    status: 'IN_STOCK',
  },
];

function itemsOk(spy?: (url: URL) => void) {
  return http.get(`${BASE}/items`, ({ request }) => {
    spy?.(new URL(request.url));
    return HttpResponse.json({ items: ITEMS, total: ITEMS.length, limit: 25, offset: 0 });
  });
}

describe('ItemsListPage', () => {
  it('lists items from the API', async () => {
    server.use(itemsOk());
    renderWithProviders(<ItemsListPage />);
    expect(await screen.findByText('Raw Steel')).toBeInTheDocument();
    expect(screen.getByText('Bottle 1L')).toBeInTheDocument();
  });

  it('sends the status filter to the server (not a client-side page filter)', async () => {
    const urls: URL[] = [];
    server.use(itemsOk((url) => urls.push(url)));
    const user = userEvent.setup();
    renderWithProviders(<ItemsListPage />);
    await screen.findByText('Raw Steel');

    await user.click(screen.getByRole('tab', { name: 'Low' }));
    await waitFor(() => expect(urls.at(-1)?.searchParams.getAll('status')).toEqual(['LOW_STOCK']));
  });

  it('Attention filter requests both low and out-of-stock', async () => {
    const urls: URL[] = [];
    server.use(itemsOk((url) => urls.push(url)));
    const user = userEvent.setup();
    renderWithProviders(<ItemsListPage />);
    await screen.findByText('Raw Steel');

    await user.click(screen.getByRole('tab', { name: 'Attention' }));
    await waitFor(() =>
      expect(urls.at(-1)?.searchParams.getAll('status')).toEqual(['LOW_STOCK', 'NO_STOCK']),
    );
  });

  it('honours the ?status=attention deep link from the dashboard', async () => {
    const urls: URL[] = [];
    server.use(itemsOk((url) => urls.push(url)));
    renderWithProviders(<ItemsListPage />, { route: '/items?status=attention' });
    await screen.findByText('Raw Steel');

    await waitFor(() =>
      expect(urls.at(-1)?.searchParams.getAll('status')).toEqual(['LOW_STOCK', 'NO_STOCK']),
    );
  });

  it('sends the type filter to the server', async () => {
    const urls: URL[] = [];
    server.use(itemsOk((url) => urls.push(url)));
    const user = userEvent.setup();
    renderWithProviders(<ItemsListPage />);
    await screen.findByText('Raw Steel');

    await user.click(screen.getByRole('tab', { name: 'Raw' }));
    await waitFor(() => expect(urls.at(-1)?.searchParams.get('type')).toBe('RAW'));
  });

  it('opens the create drawer from the page action', async () => {
    server.use(itemsOk());
    const user = userEvent.setup();
    renderWithProviders(<ItemsListPage />);
    await screen.findByText('Raw Steel');

    await user.click(screen.getByRole('button', { name: 'Add Item' }));
    expect(await screen.findByRole('dialog', { name: 'Add Item' })).toBeInTheDocument();
  });

  it('opens the create drawer when deep-linked with ?new=1', async () => {
    server.use(itemsOk());
    renderWithProviders(<ItemsListPage />, { route: '/items?new=1' });

    expect(await screen.findByRole('dialog', { name: 'Add Item' })).toBeInTheDocument();
  });

  it('shows the unit price column', async () => {
    server.use(itemsOk());
    renderWithProviders(<ItemsListPage />);
    await screen.findByText('Raw Steel');

    expect(screen.getByRole('columnheader', { name: 'Unit price' })).toBeInTheDocument();
    // ₹5.00 for Raw Steel (unit_price '5').
    expect(screen.getByText(/₹\s?5\.00/)).toBeInTheDocument();
  });

  it('shows a page error with the Request ID on failure', async () => {
    server.use(
      http.get(`${BASE}/items`, () =>
        HttpResponse.json(
          { error: { code: 'UNKNOWN_ERROR', message: 'Boom', request_id: 'req-list' } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<ItemsListPage />);
    expect(await screen.findByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText(/Request ID: req-list/)).toBeInTheDocument();
  });
});
