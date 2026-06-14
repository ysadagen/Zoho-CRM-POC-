import { describe, it, expect, vi, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';
import type { Vendor } from '@/types/api.types';

import { VendorFormDrawer } from './VendorFormDrawer';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const EXISTING: Vendor = {
  id: 'v1',
  vendor_name: 'Steelco',
  contact_person: 'Ravi',
  email: 'sales@steelco.test',
  phone: '123',
  vendor_code: 'STL-1',
  gstin: 'GST9',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

describe('VendorFormDrawer', () => {
  it('creates a vendor, fires onCreated and toasts success', async () => {
    let body: unknown;
    server.use(
      http.post(`${BASE}/vendors`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: 'new-1', vendor_name: 'Polyworks' }, { status: 201 });
      }),
    );
    const onCreated = vi.fn();
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<VendorFormDrawer mode="create" onClose={onClose} onCreated={onCreated} />);

    await user.type(screen.getByLabelText('Vendor name'), 'Polyworks');
    await user.click(screen.getByRole('button', { name: 'Add vendor' }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith('new-1'));
    expect(body).toEqual({ vendor_name: 'Polyworks' });
    expect(await screen.findByText('Polyworks added.')).toBeInTheDocument();
  });

  it('validates the required name', async () => {
    const user = userEvent.setup();
    renderWithProviders(<VendorFormDrawer mode="create" onClose={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: 'Add vendor' }));
    expect(await screen.findByText('Vendor name is required')).toBeInTheDocument();
  });

  it('shows a danger toast with the Request ID on conflict (§5.6)', async () => {
    server.use(
      http.post(`${BASE}/vendors`, () =>
        HttpResponse.json(
          { error: { code: 'DUPLICATE_VENDOR', message: 'Already exists', request_id: 'req-dv' } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<VendorFormDrawer mode="create" onClose={vi.fn()} />);
    await user.type(screen.getByLabelText('Vendor name'), 'Steelco');
    await user.click(screen.getByRole('button', { name: 'Add vendor' }));

    const toast = (await screen.findByText('Already exists')).closest('.toast');
    expect(toast).toHaveClass('danger');
    expect(toast).toHaveTextContent('Request ID: req-dv');
  });

  it('edits an existing vendor', async () => {
    let body: unknown;
    server.use(
      http.patch(`${BASE}/vendors/v1`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...EXISTING, vendor_name: 'Steelco Ltd' });
      }),
    );
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<VendorFormDrawer mode="edit" vendor={EXISTING} onClose={onClose} />);

    const name = screen.getByLabelText('Vendor name');
    expect(name).toHaveValue('Steelco');
    await user.clear(name);
    await user.type(name, 'Steelco Ltd');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(body).toMatchObject({ vendor_name: 'Steelco Ltd' });
    expect(await screen.findByText('Steelco Ltd updated.')).toBeInTheDocument();
  });
});
