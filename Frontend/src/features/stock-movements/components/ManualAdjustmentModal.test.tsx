import { describe, it, expect, vi, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { ManualAdjustmentModal } from './ManualAdjustmentModal';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const ITEMS_OK = http.get(`${BASE}/items`, () =>
  HttpResponse.json({
    items: [{ id: 'i1', sku: 'RAW-1', name: 'Raw Steel', unit_of_measure: 'kg' }],
    total: 1,
    limit: 100,
    offset: 0,
  }),
);

describe('ManualAdjustmentModal', () => {
  it('requires an item, quantity and a 10-char reason (§5)', async () => {
    server.use(ITEMS_OK);
    const user = userEvent.setup();
    renderWithProviders(<ManualAdjustmentModal onClose={vi.fn()} />);

    await user.type(screen.getByLabelText('Reason note'), 'too short');
    await user.click(screen.getByRole('button', { name: 'Record adjustment' }));

    expect(await screen.findByText('Pick an item')).toBeInTheDocument();
    expect(screen.getByText('Quantity required')).toBeInTheDocument();
    expect(screen.getByText('Add a reason of at least 10 characters')).toBeInTheDocument();
  });

  it('records an adjustment and toasts success', async () => {
    let body: unknown;
    server.use(
      ITEMS_OK,
      http.post(`${BASE}/stock-movements/adjustments`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: 'm-new', item_id: 'i1', direction: 'IN' }, { status: 201 });
      }),
    );
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<ManualAdjustmentModal onClose={onClose} />);

    await screen.findByRole('option', { name: 'RAW-1 — Raw Steel' });
    await user.selectOptions(screen.getByLabelText('Item'), 'i1');
    await user.type(screen.getByLabelText('Quantity'), '25');
    await user.type(screen.getByLabelText('Reason note'), 'Recount correction line B');
    await user.click(screen.getByRole('button', { name: 'Record adjustment' }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(body).toMatchObject({ item_id: 'i1', direction: 'IN', quantity: '25' });
    expect(await screen.findByText('Adjustment recorded.')).toBeInTheDocument();
  });

  it('adjusts a chosen lot — sends batch_id (#8)', async () => {
    let body: { batch_id?: string } | undefined;
    server.use(
      ITEMS_OK,
      http.get(`${BASE}/batches`, () =>
        HttpResponse.json({
          items: [
            {
              id: 'lot-1',
              item_id: 'i1',
              batch_number: 'LOT-1',
              quantity: '40',
              expiry_date: '2035-01-01',
              batch_status: 'QUARANTINE',
            },
          ],
          total: 1,
          limit: 100,
          offset: 0,
        }),
      ),
      http.post(`${BASE}/stock-movements/adjustments`, async ({ request }) => {
        body = (await request.json()) as typeof body;
        return HttpResponse.json({ id: 'm-new', item_id: 'i1', direction: 'OUT' }, { status: 201 });
      }),
    );
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<ManualAdjustmentModal onClose={onClose} />);

    await screen.findByRole('option', { name: 'RAW-1 — Raw Steel' });
    await user.selectOptions(screen.getByLabelText('Item'), 'i1');
    // The lot picker populates from the selected item's lots.
    await screen.findByRole('option', { name: /LOT-1/ });
    await user.selectOptions(screen.getByLabelText('Lot (optional)'), 'lot-1');
    await user.selectOptions(screen.getByLabelText('Direction'), 'OUT');
    await user.type(screen.getByLabelText('Quantity'), '10');
    await user.type(screen.getByLabelText('Reason note'), 'Damaged units in this lot');
    await user.click(screen.getByRole('button', { name: 'Record adjustment' }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(body?.batch_id).toBe('lot-1');
  });

  it('surfaces INSUFFICIENT_STOCK as a danger toast with the Request ID', async () => {
    server.use(
      ITEMS_OK,
      http.post(`${BASE}/stock-movements/adjustments`, () =>
        HttpResponse.json(
          { error: { code: 'INSUFFICIENT_STOCK', message: 'Insufficient stock', request_id: 'req-adj' } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<ManualAdjustmentModal onClose={vi.fn()} />);

    await screen.findByRole('option', { name: 'RAW-1 — Raw Steel' });
    await user.selectOptions(screen.getByLabelText('Item'), 'i1');
    await user.selectOptions(screen.getByLabelText('Direction'), 'OUT');
    await user.type(screen.getByLabelText('Quantity'), '999');
    await user.type(screen.getByLabelText('Reason note'), 'Write-off of damaged stock');
    await user.click(screen.getByRole('button', { name: 'Record adjustment' }));

    const toast = (await screen.findByText('Insufficient stock')).closest('.toast');
    expect(toast).toHaveClass('danger');
    expect(toast).toHaveTextContent('Request ID: req-adj');
  });
});
