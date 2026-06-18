import { describe, it, expect, beforeAll, afterAll, afterEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders, seedSession } from '@/test/utils';

import { StageTransitionModal } from './StageTransitionModal';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('StageTransitionModal', () => {
  it('requires a won value when moving to WON', async () => {
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(
      <StageTransitionModal leadId="l1" currentStage="NEGOTIATION" onClose={() => {}} />,
    );
    // NEGOTIATION → [WON, LOST]; WON is the default, so the value field shows.
    await user.click(screen.getByRole('button', { name: 'Confirm' }));
    expect(await screen.findByText('Won value is required')).toBeInTheDocument();
  });

  it('submits a valid WON transition and closes', async () => {
    let body: Record<string, unknown> | null = null;
    server.use(
      http.post(`${BASE}/leads/l1/transition`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: 'l1', lead_number: 'LD-1', stage: 'WON' });
      }),
    );
    seedSession();
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <StageTransitionModal leadId="l1" currentStage="NEGOTIATION" onClose={onClose} />,
    );

    await user.type(screen.getByLabelText('Won value'), '500000');
    await user.click(screen.getByRole('button', { name: 'Confirm' }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(body).toMatchObject({ to_stage: 'WON', won_value: '500000' });
  });
});
