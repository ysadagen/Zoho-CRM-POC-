import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';
import type { VendorItemTerm } from '@/types/api.types';

import { VendorTermsTab } from './VendorTermsTab';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const TERM: VendorItemTerm = {
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
};

const ITEMS_OK = http.get(`${BASE}/items`, () =>
  HttpResponse.json({
    items: [{ id: 'i1', sku: 'RAW-1', name: 'Raw Steel', unit_of_measure: 'kg' }],
    total: 1,
    limit: 100,
    offset: 0,
  }),
);

describe('VendorTermsTab', () => {
  it('renders linked terms with the resolved item name', async () => {
    server.use(ITEMS_OK);
    renderWithProviders(<VendorTermsTab vendorId="v1" terms={[TERM]} loading={false} />);
    expect(await screen.findByText('RAW-1 — Raw Steel')).toBeInTheDocument();
    expect(screen.getByText('5.00%')).toBeInTheDocument();
  });

  it('opens the link-item drawer', async () => {
    server.use(ITEMS_OK);
    const user = userEvent.setup();
    renderWithProviders(<VendorTermsTab vendorId="v1" terms={[TERM]} loading={false} />);
    await screen.findByText('RAW-1 — Raw Steel');

    await user.click(screen.getByRole('button', { name: 'Link item' }));
    expect(await screen.findByRole('dialog', { name: 'Link item' })).toBeInTheDocument();
  });

  it('removes a term after confirming', async () => {
    let deleted = false;
    server.use(
      ITEMS_OK,
      http.delete(`${BASE}/vendors/v1/terms/t1`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<VendorTermsTab vendorId="v1" terms={[TERM]} loading={false} />);
    await screen.findByText('RAW-1 — Raw Steel');

    await user.click(screen.getByRole('button', { name: 'Remove' }));
    const dialog = await screen.findByRole('dialog', { name: 'Remove linked item' });
    await user.click(within(dialog).getByRole('button', { name: 'Remove' }));

    await waitFor(() => expect(deleted).toBe(true));
    expect(await screen.findByText('Item unlinked.')).toBeInTheDocument();
  });
});
