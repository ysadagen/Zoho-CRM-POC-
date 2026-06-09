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

  it('filters by status on the client', async () => {
    server.use(itemsOk());
    const user = userEvent.setup();
    renderWithProviders(<ItemsListPage />);
    await screen.findByText('Raw Steel');

    await user.click(screen.getByRole('tab', { name: 'Low' }));
    expect(screen.getByText('Raw Steel')).toBeInTheDocument();
    expect(screen.queryByText('Bottle 1L')).not.toBeInTheDocument();
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
