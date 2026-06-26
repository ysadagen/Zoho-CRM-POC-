import { describe, it, expect, vi, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';
import type { Customer } from '@/types/api.types';

import { CustomerFormDrawer } from './CustomerFormDrawer';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const EXISTING: Customer = {
  id: 'c1',
  company_name: 'Acme',
  contact_person: 'Anita',
  email: 'ops@acme.test',
  phone: '123',
  customer_code: 'ACME-1',
  gstin: null,
  is_privileged: false,
  is_active: true,
  address: null,
  state: null,
  city: null,
  district: null,
  pincode: null,
  notes: null,
  customer_type: 'RETAILER',
  competitive_risk_level: 'NONE',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

describe('CustomerFormDrawer', () => {
  it('creates a customer, fires onCreated and toasts success', async () => {
    let body: unknown;
    server.use(
      http.post(`${BASE}/customers`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: 'new-1', company_name: 'Globex' }, { status: 201 });
      }),
    );
    const onCreated = vi.fn();
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<CustomerFormDrawer mode="create" onClose={onClose} onCreated={onCreated} />);

    await user.type(screen.getByLabelText('Company name'), 'Globex');
    await user.click(screen.getByRole('button', { name: 'Add customer' }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith('new-1'));
    expect(body).toMatchObject({ company_name: 'Globex', is_privileged: false });
    expect(await screen.findByText('Globex added.')).toBeInTheDocument();
  });

  it('validates the required name and email format', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CustomerFormDrawer mode="create" onClose={vi.fn()} />);

    await user.type(screen.getByLabelText('Email'), 'not-an-email');
    await user.click(screen.getByRole('button', { name: 'Add customer' }));

    expect(await screen.findByText('Company name is required')).toBeInTheDocument();
    expect(screen.getByText('Enter a valid email')).toBeInTheDocument();
  });

  it('shows a danger toast with the Request ID on a conflict (§5.6)', async () => {
    server.use(
      http.post(`${BASE}/customers`, () =>
        HttpResponse.json(
          { error: { code: 'DUPLICATE_CUSTOMER', message: 'Already exists', request_id: 'req-dc' } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<CustomerFormDrawer mode="create" onClose={vi.fn()} />);

    await user.type(screen.getByLabelText('Company name'), 'Acme');
    await user.click(screen.getByRole('button', { name: 'Add customer' }));

    const toast = (await screen.findByText('Already exists')).closest('.toast');
    expect(toast).toHaveClass('danger');
    expect(toast).toHaveTextContent('Request ID: req-dc');
  });

  it('edits and patches an existing customer', async () => {
    let body: unknown;
    server.use(
      http.patch(`${BASE}/customers/c1`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...EXISTING, company_name: 'Acme Corp' });
      }),
    );
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<CustomerFormDrawer mode="edit" customer={EXISTING} onClose={onClose} />);

    const name = screen.getByLabelText('Company name');
    expect(name).toHaveValue('Acme');
    await user.clear(name);
    await user.type(name, 'Acme Corp');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(body).toMatchObject({ company_name: 'Acme Corp' });
    expect(await screen.findByText('Acme Corp updated.')).toBeInTheDocument();
  });
});
