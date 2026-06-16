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

/** The drawer fetches RAW items (for the ingredient picker) when type=FINISHED. */
function rawItemsHandler(items: unknown[] = []) {
  return http.get(`${BASE}/items`, () =>
    HttpResponse.json({ items, total: items.length, limit: 100, offset: 0 }),
  );
}

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
  storage_condition: null,
  shelf_life_days: null,
  raw_detail: null,
  finished_detail: null,
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

  it('reveals finished-product fields on type change and sends the detail block', async () => {
    let body: unknown;
    server.use(
      rawItemsHandler(),
      http.post(`${BASE}/items`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          { id: 'f1', sku: 'PCM-500', name: 'Paracetamol 500', created_at: 'now' },
          { status: 201 },
        );
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ItemFormDrawer mode="create" onClose={vi.fn()} onCreated={vi.fn()} />);

    // RAW by default — finished fields are hidden until the type flips.
    expect(screen.queryByLabelText('Dosage form')).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('Type'), 'FINISHED');
    expect(screen.getByLabelText('Dosage form')).toBeInTheDocument();

    await user.type(screen.getByLabelText('SKU'), 'PCM-500');
    await user.type(screen.getByLabelText('Name'), 'Paracetamol 500');
    await user.type(screen.getByLabelText('Category'), 'Analgesic');
    await user.type(screen.getByLabelText('Unit price'), '20');
    await user.selectOptions(screen.getByLabelText('Storage condition'), 'COLD_CHAIN_2_8');
    await user.type(screen.getByLabelText('Generic name'), 'Paracetamol');
    await user.selectOptions(screen.getByLabelText('Dosage form'), 'TABLET');
    await user.click(screen.getByLabelText('Prescription required'));
    await user.click(screen.getByRole('button', { name: 'Create item' }));

    await waitFor(() => expect(body).toBeTruthy());
    expect(body).toMatchObject({
      type: 'FINISHED',
      storage_condition: 'COLD_CHAIN_2_8',
      finished_detail: {
        generic_name: 'Paracetamol',
        dosage_form: 'TABLET',
        is_prescription_required: true,
      },
    });
  });

  it('lets ingredients be picked from raw materials with the unit auto-fetched', async () => {
    let body: unknown;
    server.use(
      rawItemsHandler([
        { id: 'r1', sku: 'RAW-LAC', name: 'Lactose', type: 'RAW', unit_of_measure: 'g' },
      ]),
      http.post(`${BASE}/items`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          { id: 'f2', sku: 'TAB-1', name: 'Tablet', created_at: 'now' },
          { status: 201 },
        );
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ItemFormDrawer mode="create" onClose={vi.fn()} onCreated={vi.fn()} />);

    await user.selectOptions(screen.getByLabelText('Type'), 'FINISHED');
    // The raw material is available to pick from the ingredient combobox (a
    // datalist option, so hidden in the a11y tree); awaiting it also lets the
    // raw-materials fetch resolve before we rely on the unit auto-fill.
    expect(await screen.findByRole('option', { name: 'Lactose', hidden: true })).toBeInTheDocument();

    await user.type(screen.getByLabelText('SKU'), 'TAB-1');
    await user.type(screen.getByLabelText('Name'), 'Tablet');
    await user.type(screen.getByLabelText('Category'), 'Tablets');
    await user.type(screen.getByLabelText('Unit price'), '10');
    // Picking the raw material auto-fetches its unit (g).
    await user.type(screen.getByLabelText('Ingredient name 1'), 'Lactose');
    expect(screen.getByLabelText('Ingredient unit 1')).toHaveValue('g');
    await user.type(screen.getByLabelText('Ingredient quantity 1'), '200');
    await user.click(screen.getByRole('button', { name: 'Create item' }));

    await waitFor(() => expect(body).toBeTruthy());
    expect(body).toMatchObject({
      type: 'FINISHED',
      finished_detail: { ingredients: JSON.stringify([{ name: 'Lactose', qty: '200', unit: 'g' }]) },
    });
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
      rawItemsHandler(),
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
