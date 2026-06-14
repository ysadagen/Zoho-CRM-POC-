import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { CustomersListPage } from './CustomersListPage';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const CUSTOMERS = [
  {
    id: 'c1',
    company_name: 'Acme Distributors',
    contact_person: 'Anita',
    email: 'ops@acme.test',
    phone: '123',
    customer_code: 'ACME-1',
    gstin: null,
    is_privileged: true,
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

function customersOk() {
  return http.get(`${BASE}/customers`, () =>
    HttpResponse.json({ items: CUSTOMERS, total: 1, limit: 25, offset: 0 }),
  );
}

describe('CustomersListPage', () => {
  it('lists customers from the API', async () => {
    server.use(customersOk());
    renderWithProviders(<CustomersListPage />);
    expect(await screen.findByText('Acme Distributors')).toBeInTheDocument();
    expect(screen.getByText('Privileged')).toBeInTheDocument();
  });

  it('opens the create drawer from the page action', async () => {
    server.use(customersOk());
    const user = userEvent.setup();
    renderWithProviders(<CustomersListPage />);
    await screen.findByText('Acme Distributors');

    await user.click(screen.getByRole('button', { name: 'Add Customer' }));
    expect(await screen.findByRole('dialog', { name: 'Add Customer' })).toBeInTheDocument();
  });

  it('shows a page error with the Request ID on failure', async () => {
    server.use(
      http.get(`${BASE}/customers`, () =>
        HttpResponse.json(
          { error: { code: 'UNKNOWN_ERROR', message: 'Boom', request_id: 'req-cl' } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<CustomersListPage />);
    expect(await screen.findByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText(/Request ID: req-cl/)).toBeInTheDocument();
  });
});
