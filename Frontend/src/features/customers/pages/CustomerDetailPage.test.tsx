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

const CUSTOMER = {
  id: 'c1',
  company_name: 'Acme Distributors',
  contact_person: 'Anita',
  email: 'ops@acme.test',
  phone: '123',
  customer_code: 'ACME-1',
  gstin: 'GST123',
  is_privileged: true,
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-05-01T00:00:00Z',
};

const ORDERS = [
  {
    id: 'so1',
    so_number: 'SO-202605-000001',
    customer_id: 'c1',
    order_date: '2026-05-10',
    expected_delivery_date: null,
    shipped_date: null,
    status: 'DRAFT',
    subtotal: '100',
    total: '100',
    notes: null,
    items: [],
    created_at: '2026-05-10T00:00:00Z',
    updated_at: '2026-05-10T00:00:00Z',
  },
];

const ACTIVITY = {
  id: 'act1',
  customer_id: 'c1',
  lead_id: null,
  type: 'VISIT',
  occurred_at: '2026-05-20T10:00:00Z',
  duration_minutes: 30,
  remarks: 'Quarterly site visit',
  created_by_user_id: 'u-1',
  created_at: '2026-05-20T10:00:00Z',
};

function handlers() {
  return [
    http.get(`${BASE}/customers/c1`, () => HttpResponse.json(CUSTOMER)),
    http.get(`${BASE}/sales-orders`, () =>
      HttpResponse.json({ items: ORDERS, total: 1, limit: 50, offset: 0 }),
    ),
    http.get(`${BASE}/activities`, () =>
      HttpResponse.json({ items: [ACTIVITY], total: 1, limit: 50, offset: 0 }),
    ),
  ];
}

describe('CustomerDetailPage', () => {
  it('shows the profile with master fields', async () => {
    server.use(...handlers());
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/customers/c1' });

    expect(await screen.findByRole('heading', { name: 'Acme Distributors' })).toBeInTheDocument();
    expect(screen.getByText('ops@acme.test')).toBeInTheDocument();
  });

  it('switches to the sales-orders tab', async () => {
    server.use(...handlers());
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/customers/c1' });
    await screen.findByRole('heading', { name: 'Acme Distributors' });

    await user.click(screen.getByRole('tab', { name: 'Sales orders' }));
    expect(await screen.findByText('SO-202605-000001')).toBeInTheDocument();
  });

  it('lists the customer activities on the Activity tab', async () => {
    server.use(...handlers());
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/customers/c1' });
    await screen.findByRole('heading', { name: 'Acme Distributors' });

    await user.click(screen.getByRole('tab', { name: 'Activity' }));
    expect(await screen.findByText('Quarterly site visit')).toBeInTheDocument();
  });

  it('opens the Log Activity modal from the Activity tab', async () => {
    server.use(...handlers());
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/customers/c1' });
    await screen.findByRole('heading', { name: 'Acme Distributors' });

    await user.click(screen.getByRole('tab', { name: 'Activity' }));
    await user.click(screen.getByRole('button', { name: 'Log activity' }));
    expect(await screen.findByRole('dialog', { name: 'Log Activity' })).toBeInTheDocument();
  });

  it('opens the edit drawer prefilled', async () => {
    server.use(...handlers());
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/customers/c1' });
    await screen.findByRole('heading', { name: 'Acme Distributors' });

    await user.click(screen.getByRole('button', { name: 'Edit' }));
    expect(await screen.findByRole('dialog', { name: 'Edit Customer' })).toBeInTheDocument();
    expect(screen.getByLabelText('Company name')).toHaveValue('Acme Distributors');
  });

  it('shows a page error with the Request ID when the customer fails to load', async () => {
    server.use(
      http.get(`${BASE}/customers/c1`, () =>
        HttpResponse.json(
          { error: { code: 'CUSTOMER_NOT_FOUND', message: 'Not found', request_id: 'req-c404' } },
          { status: 404 },
        ),
      ),
      http.get(`${BASE}/sales-orders`, () =>
        HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 }),
      ),
    );
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/customers/c1' });

    await waitFor(() => expect(screen.getByText(/Request ID: req-c404/)).toBeInTheDocument());
  });
});
