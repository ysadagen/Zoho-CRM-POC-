import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
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

const LEAD_DETAIL = {
  id: 'l1',
  lead_number: 'LD-202606-000001',
  stage: 'NEW',
  contact_name: 'Ravi Kumar',
  source: 'FIELD_VISIT',
  assigned_to_user_id: 'u-1',
  customer_id: null,
  phone: '99999',
  email: null,
  item_id: null,
  quantity: null,
  estimated_budget: null,
  dealer_potential: null,
  required_by_date: null,
  state: 'Odisha',
  district: 'Jajpur',
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
  stage_history: [
    {
      id: 'h1',
      from_stage: null,
      to_stage: 'NEW',
      changed_at: '2026-06-01T00:00:00Z',
      changed_by_user_id: 'u-1',
      remark: null,
    },
  ],
};

const SCORE_DETAIL = {
  lead_id: 'l1',
  config_version: 1,
  computed_at: '2026-06-18T00:00:00Z',
  components: { urgency: 100, location: 100, contribution_margin: 100, quantity: 100, product_margin: 100 },
  total_score: 100,
  classification: 'HOT',
  defaults_applied: [],
  history: [],
};

function handlers() {
  return [
    http.get(`${BACKEND}/leads/l1`, () => HttpResponse.json(LEAD_DETAIL)),
    http.get(`${INTEL}/intelligence/lead-scores/l1`, () => HttpResponse.json(SCORE_DETAIL)),
    http.get(`${BACKEND}/activities`, () =>
      HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 }),
    ),
  ];
}

describe('LeadDetailPage', () => {
  it('shows the lead, its live score breakdown, and stage history', async () => {
    server.use(...handlers());
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/leads/l1' });

    expect(await screen.findByText(/LD-202606-000001/)).toBeInTheDocument();
    expect(await screen.findByText('100.00')).toBeInTheDocument(); // total score
    expect(screen.getByText('Urgency')).toBeInTheDocument();
  });

  it('opens the guarded stage-transition modal', async () => {
    server.use(...handlers());
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/leads/l1' });
    await screen.findByText(/LD-202606-000001/);

    await user.click(screen.getByRole('button', { name: 'Change stage' }));
    expect(await screen.findByRole('dialog', { name: 'Change stage' })).toBeInTheDocument();
  });
});
