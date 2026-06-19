import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { AppRouter } from '@/app/router';
import { clearSession } from '@/auth/token-storage';
import { renderWithProviders, seedSession } from '@/test/utils';

const BACKEND = 'http://localhost:8000/api/v1';
const INTEL = 'http://localhost:8002/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => {
  server.resetHandlers();
  clearSession();
});
afterAll(() => server.close());

const LEAD = {
  id: 'l1',
  lead_number: 'LD-202606-000001',
  stage: 'NEW',
  contact_name: 'Ravi Kumar',
  source: 'FIELD_VISIT',
  assigned_to_user_id: 'u-1',
  customer_id: null,
  phone: null,
  email: null,
  item_id: null,
  quantity: null,
  estimated_budget: null,
  dealer_potential: null,
  required_by_date: null,
  state: null,
  district: null,
  city: null,
  pincode: null,
  won_value: null,
  won_at: null,
  lost_at: null,
  lost_reason: null,
  notes: null,
  is_active: true,
  created_by_user_id: 'u-1',
  updated_by_user_id: 'u-1',
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
};

const SCORE_ITEM = {
  lead_id: 'l1',
  lead_number: 'LD-202606-000001',
  contact_name: 'Ravi Kumar',
  assigned_to_user_id: 'u-1',
  config_version: 1,
  computed_at: '2026-06-18T00:00:00Z',
  components: { urgency: 100, location: 100, contribution_margin: 100, quantity: 100, product_margin: 100 },
  total_score: 100,
  classification: 'HOT',
  defaults_applied: [],
};

function okHandlers() {
  return [
    http.get(`${BACKEND}/leads`, () =>
      HttpResponse.json({ items: [LEAD], total: 1, limit: 25, offset: 0 }),
    ),
    http.get(`${INTEL}/intelligence/lead-scores`, () =>
      HttpResponse.json({ items: [SCORE_ITEM], total: 1, limit: 100, offset: 0 }),
    ),
  ];
}

describe('LeadsListPage', () => {
  it('lists leads and joins the Hot/Medium/Cold badge from the Intelligence service', async () => {
    server.use(...okHandlers());
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/leads' });
    expect(await screen.findByText('LD-202606-000001')).toBeInTheDocument();
    // "Hot" also appears as a filter <option>; scope to the table badge.
    expect(await screen.findByText('Hot', { selector: '.badge' })).toHaveClass('bd-danger');
  });

  it('opens the create drawer from the page action', async () => {
    server.use(...okHandlers());
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/leads' });
    await screen.findByText('LD-202606-000001');
    await user.click(screen.getByRole('button', { name: 'Add Lead' }));
    expect(await screen.findByRole('dialog', { name: 'Add Lead' })).toBeInTheDocument();
  });

  it('shows a page error with the Request ID when leads fail to load', async () => {
    server.use(
      http.get(`${BACKEND}/leads`, () =>
        HttpResponse.json(
          { error: { code: 'UNKNOWN_ERROR', message: 'Boom', request_id: 'req-ll' } },
          { status: 500 },
        ),
      ),
      // The score join fires in parallel; mock it so it doesn't hit the network.
      http.get(`${INTEL}/intelligence/lead-scores`, () =>
        HttpResponse.json({ items: [], total: 0, limit: 100, offset: 0 }),
      ),
    );
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/leads' });
    await waitFor(() => expect(screen.getByText(/Request ID: req-ll/)).toBeInTheDocument());
  });
});
