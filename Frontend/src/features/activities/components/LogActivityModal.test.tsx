import { describe, it, expect, vi, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { LogActivityModal } from './LogActivityModal';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('LogActivityModal', () => {
  it('submits the form with the subject id and toasts success', async () => {
    let body: Record<string, unknown> | undefined;
    server.use(
      http.post(`${BASE}/activities`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            id: 'a-1',
            type: 'CALL',
            rep_user_id: 'u-1',
            customer_id: 'c1',
            lead_id: null,
            occurred_at: body.occurred_at,
            duration_minutes: 30,
            remarks: 'Spoke about reorder',
            created_by_user_id: 'u-1',
            created_at: '2026-06-18T00:00:00Z',
          },
          { status: 201 },
        );
      }),
    );
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<LogActivityModal customerId="c1" onClose={onClose} />);

    await user.selectOptions(screen.getByLabelText('Type'), 'CALL');
    await user.type(screen.getByLabelText('When'), '2026-06-17T10:30');
    await user.type(screen.getByLabelText('Duration (minutes)'), '30');
    await user.type(screen.getByLabelText('Remarks'), 'Spoke about reorder');
    await user.click(screen.getByRole('button', { name: 'Log activity' }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(body).toMatchObject({
      type: 'CALL',
      customer_id: 'c1',
      duration_minutes: 30,
      remarks: 'Spoke about reorder',
    });
    expect(typeof body?.occurred_at).toBe('string');
    expect(await screen.findByText('Activity logged.')).toBeInTheDocument();
  });

  it('shows a danger toast with the Request ID on a 422 (§5.6)', async () => {
    server.use(
      http.post(`${BASE}/activities`, () =>
        HttpResponse.json(
          { error: { code: 'VALIDATION_ERROR', message: 'Invalid activity', request_id: 'req-act' } },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<LogActivityModal leadId="l1" onClose={vi.fn()} />);

    await user.type(screen.getByLabelText('When'), '2026-06-17T10:30');
    await user.click(screen.getByRole('button', { name: 'Log activity' }));

    const toast = (await screen.findByText('Invalid activity')).closest('.toast');
    expect(toast).toHaveClass('danger');
    expect(toast).toHaveTextContent('Request ID: req-act');
  });
});
