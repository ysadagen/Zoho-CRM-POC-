import { describe, it, expect, beforeAll, afterAll, afterEach, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { BatchFormDrawer } from './BatchFormDrawer';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const ITEMS = [{ id: 'i1', sku: 'RAW-1', name: 'Raw Steel', unit_of_measure: 'kg', unit_price: '750' }];

function itemsOk() {
  return http.get(`${BASE}/items`, () =>
    HttpResponse.json({ items: ITEMS, total: 1, limit: 100, offset: 0 }),
  );
}

async function fillRequired(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await screen.findByRole('option', { name: 'RAW-1 — Raw Steel' });
  await user.selectOptions(screen.getByLabelText('Item'), 'i1');
  await user.type(screen.getByLabelText('Batch number'), 'LOT-A');
  await user.type(screen.getByLabelText('Quantity'), '40');
  fireEvent.change(screen.getByLabelText('Expiry date'), { target: { value: '2030-01-01' } });
}

describe('BatchFormDrawer', () => {
  it('records a lot and posts the opening-balance payload', async () => {
    let body: unknown;
    server.use(
      itemsOk(),
      http.post(`${BASE}/batches`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: 'b1', batch_number: 'LOT-A' }, { status: 201 });
      }),
    );
    const onClose = vi.fn();
    const onCreated = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<BatchFormDrawer onClose={onClose} onCreated={onCreated} />);

    await fillRequired(user);
    // Selecting the item auto-fills the lot's unit cost from its catalog price.
    expect(screen.getByLabelText('Unit cost')).toHaveValue(750);
    await user.click(screen.getByRole('button', { name: 'Record lot' }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith('b1'));
    expect(onClose).toHaveBeenCalled();
    expect(body).toMatchObject({
      item_id: 'i1',
      batch_number: 'LOT-A',
      quantity: '40',
      expiry_date: '2030-01-01',
      batch_status: 'QUARANTINE',
    });
    expect(await screen.findByText('Lot LOT-A recorded.')).toBeInTheDocument();
  });

  it('blocks submit and shows messages when required fields are empty', async () => {
    let called = false;
    server.use(
      itemsOk(),
      http.post(`${BASE}/batches`, () => {
        called = true;
        return HttpResponse.json({ id: 'x', batch_number: 'x' }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<BatchFormDrawer onClose={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Record lot' }));

    expect(await screen.findByText('Pick an item')).toBeInTheDocument();
    expect(screen.getByText('Batch number is required')).toBeInTheDocument();
    expect(screen.getByText('Quantity is required')).toBeInTheDocument();
    expect(screen.getByText('Expiry date is required')).toBeInTheDocument();
    expect(called).toBe(false);
  });

  it('shows a danger toast with the Request ID when the lot exceeds unbatched stock (§5.6)', async () => {
    server.use(
      itemsOk(),
      http.post(`${BASE}/batches`, () =>
        HttpResponse.json(
          {
            error: {
              code: 'BATCH_EXCEEDS_UNBATCHED_STOCK',
              message: 'Lot quantity exceeds the item unbatched stock',
              request_id: 'req-batch',
            },
          },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<BatchFormDrawer onClose={vi.fn()} />);

    await fillRequired(user);
    await user.click(screen.getByRole('button', { name: 'Record lot' }));

    // The §5.6 non-negotiable: the danger toast carries the Request ID. The id
    // sits in its own `.mono` span, so match the message then assert the id via
    // the toast's text content (mirrors the items conflict test).
    const toast = (
      await screen.findByText('Lot quantity exceeds the item unbatched stock')
    ).closest('.toast');
    expect(toast).toHaveTextContent('Request ID: req-batch');
  });
});
