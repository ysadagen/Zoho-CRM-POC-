import { describe, it, expect, vi, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';
import type { Item } from '@/types/api.types';

import { ItemFormDrawer } from './ItemFormDrawer';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const EXISTING: Item = {
  id: 'i1',
  sku: 'BOT-1L',
  name: '1L Bottle',
  description: 'Round',
  type: 'FINISHED',
  category: 'Bottles',
  unit_of_measure: 'pcs',
  stock_quantity: '500',
  reorder_threshold: '100',
  unit_price: '45',
  status: 'IN_STOCK',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

describe('ItemFormDrawer — create', () => {
  it('creates an item, fires onCreated/onClose and toasts success', async () => {
    let body: unknown;
    server.use(
      http.post(`${BASE}/items`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          { id: 'new-1', sku: 'BOT-1L', name: '1L Bottle', created_at: 'now' },
          { status: 201 },
        );
      }),
    );
    const onClose = vi.fn();
    const onCreated = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<ItemFormDrawer mode="create" onClose={onClose} onCreated={onCreated} />);

    await user.type(screen.getByLabelText('SKU'), 'BOT-1L');
    await user.type(screen.getByLabelText('Name'), '1L Bottle');
    await user.type(screen.getByLabelText('Category'), 'Bottles');
    await user.type(screen.getByLabelText('Unit price'), '45');
    await user.click(screen.getByRole('button', { name: 'Create item' }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith('new-1'));
    expect(onClose).toHaveBeenCalled();
    expect(body).toMatchObject({
      sku: 'BOT-1L',
      name: '1L Bottle',
      type: 'RAW',
      category: 'Bottles',
      unit_price: '45',
    });
    expect(await screen.findByText('1L Bottle created.')).toBeInTheDocument();
  });

  it('blocks submit and shows messages when required fields are empty', async () => {
    let called = false;
    server.use(
      http.post(`${BASE}/items`, () => {
        called = true;
        return HttpResponse.json({ id: 'x', sku: 's', name: 'n', created_at: 'now' }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ItemFormDrawer mode="create" onClose={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Create item' }));

    expect(await screen.findByText('SKU is required')).toBeInTheDocument();
    expect(screen.getByText('Name is required')).toBeInTheDocument();
    expect(screen.getByText('Category is required')).toBeInTheDocument();
    expect(screen.getByText('Unit price is required')).toBeInTheDocument();
    expect(called).toBe(false);
  });

  it('shows a danger toast with the Request ID on a server conflict (§5.6)', async () => {
    server.use(
      http.post(`${BASE}/items`, () =>
        HttpResponse.json(
          { error: { code: 'DUPLICATE_SKU', message: 'SKU already taken', request_id: 'req-dup' } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<ItemFormDrawer mode="create" onClose={vi.fn()} />);

    await user.type(screen.getByLabelText('SKU'), 'BOT-1L');
    await user.type(screen.getByLabelText('Name'), '1L Bottle');
    await user.type(screen.getByLabelText('Category'), 'Bottles');
    await user.type(screen.getByLabelText('Unit price'), '45');
    await user.click(screen.getByRole('button', { name: 'Create item' }));

    const toast = (await screen.findByText('SKU already taken')).closest('.toast');
    expect(toast).toHaveClass('danger');
    expect(toast).toHaveTextContent('Request ID: req-dup');
  });

  it('routes a 422 field error to the matching field', async () => {
    server.use(
      http.post(`${BASE}/items`, () =>
        HttpResponse.json(
          { detail: [{ loc: ['body', 'sku'], msg: 'SKU has a bad format', type: 'value_error' }] },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<ItemFormDrawer mode="create" onClose={vi.fn()} />);

    await user.type(screen.getByLabelText('SKU'), 'bad sku');
    await user.type(screen.getByLabelText('Name'), '1L Bottle');
    await user.type(screen.getByLabelText('Category'), 'Bottles');
    await user.type(screen.getByLabelText('Unit price'), '45');
    await user.click(screen.getByRole('button', { name: 'Create item' }));

    expect(await screen.findByText('SKU has a bad format')).toBeInTheDocument();
  });
});

describe('ItemFormDrawer — edit', () => {
  it('prefills, patches PATCH-safe fields and toasts success', async () => {
    let body: unknown;
    server.use(
      http.patch(`${BASE}/items/i1`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...EXISTING, name: 'Renamed Bottle' });
      }),
    );
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<ItemFormDrawer mode="edit" item={EXISTING} onClose={onClose} />);

    // SKU/type are read-only in edit mode.
    expect(screen.queryByLabelText('SKU')).not.toBeInTheDocument();
    const name = screen.getByLabelText('Name');
    expect(name).toHaveValue('1L Bottle');

    await user.clear(name);
    await user.type(name, 'Renamed Bottle');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(body).toMatchObject({ name: 'Renamed Bottle', category: 'Bottles', unit_of_measure: 'pcs' });
    expect(body).not.toHaveProperty('sku');
    expect(await screen.findByText('Renamed Bottle updated.')).toBeInTheDocument();
  });
});
