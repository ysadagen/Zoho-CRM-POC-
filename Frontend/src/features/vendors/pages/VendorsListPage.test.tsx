import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { VendorsListPage } from './VendorsListPage';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const VENDORS = [
  {
    id: 'v1',
    vendor_name: 'Steelcraft Co.',
    contact_person: 'Ravi',
    email: 'sales@steelcraft.test',
    phone: '123',
    vendor_code: 'STL-1',
    gstin: null,
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

function vendorsOk() {
  return http.get(`${BASE}/vendors`, () =>
    HttpResponse.json({ items: VENDORS, total: 1, limit: 25, offset: 0 }),
  );
}

describe('VendorsListPage', () => {
  it('lists vendors from the API', async () => {
    server.use(vendorsOk());
    renderWithProviders(<VendorsListPage />);
    expect(await screen.findByText('Steelcraft Co.')).toBeInTheDocument();
  });

  it('opens the create drawer', async () => {
    server.use(vendorsOk());
    const user = userEvent.setup();
    renderWithProviders(<VendorsListPage />);
    await screen.findByText('Steelcraft Co.');

    await user.click(screen.getByRole('button', { name: 'Add Vendor' }));
    expect(await screen.findByRole('dialog', { name: 'Add Vendor' })).toBeInTheDocument();
  });

  it('shows a page error with the Request ID on failure', async () => {
    server.use(
      http.get(`${BASE}/vendors`, () =>
        HttpResponse.json(
          { error: { code: 'UNKNOWN_ERROR', message: 'Boom', request_id: 'req-vl' } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<VendorsListPage />);
    expect(await screen.findByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText(/Request ID: req-vl/)).toBeInTheDocument();
  });
});
