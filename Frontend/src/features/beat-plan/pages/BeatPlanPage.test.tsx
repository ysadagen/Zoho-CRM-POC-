import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { BeatPlanPage } from './BeatPlanPage';

const BACKEND = 'http://localhost:8000/api/v1';
const INTEL = 'http://localhost:8002/api/v1';

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const REPS = [
  {
    id: 'rep-1',
    email: 'ravi@adagen.in',
    full_name: 'Ravi Menon',
    is_admin: false,
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

const PLAN = {
  rep_user_id: 'rep-1',
  generated_at: '2026-06-18T00:00:00Z',
  max_visits: 8,
  clusters: [
    { district: 'Raigarh', customer_count: 4, lds: 0.62, cluster_opportunity: true },
  ],
  suggested_beat: [
    {
      customer_id: 'cust-1',
      company_name: 'Acme Distributors',
      district: 'Raigarh',
      customer_type: 'DEALER',
      vps: 82,
      priority: 'CRITICAL',
      breakdown: {
        revenue_score: 30,
        visit_gap_score: 25,
        customer_type_score: 15,
        location_density_score: 12,
      },
      days_since_last_visit: 45,
      revenue_90d: '125000.00',
    },
  ],
  all_customers: [
    {
      customer_id: 'cust-1',
      company_name: 'Acme Distributors',
      district: 'Raigarh',
      customer_type: 'DEALER',
      vps: 82,
      priority: 'CRITICAL',
      breakdown: {
        revenue_score: 30,
        visit_gap_score: 25,
        customer_type_score: 15,
        location_density_score: 12,
      },
      days_since_last_visit: 45,
      revenue_90d: '125000.00',
    },
  ],
};

function repsOk() {
  return http.get(`${BACKEND}/users`, () =>
    HttpResponse.json({ items: REPS, total: 1, limit: 100, offset: 0 }),
  );
}

describe('BeatPlanPage', () => {
  it('loads reps and a rep selection loads the beat plan', async () => {
    server.use(
      repsOk(),
      http.get(`${INTEL}/intelligence/beat-plan`, () => HttpResponse.json(PLAN)),
    );
    const user = userEvent.setup();
    renderWithProviders(<BeatPlanPage />);

    const select = await screen.findByLabelText('Sales rep');
    await screen.findByRole('option', { name: 'ravi@adagen.in' });
    await user.selectOptions(select, 'rep-1');

    // Customer + its priority badge from the Intelligence plan (appears in
    // both the suggested-beat and the full ranked tables).
    expect((await screen.findAllByText('Acme Distributors')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Critical').length).toBeGreaterThan(0);
    // A district cluster (district name shows in clusters + customer tables).
    expect(screen.getAllByText('Raigarh').length).toBeGreaterThan(0);
    expect(screen.getByText('Cluster opportunity')).toBeInTheDocument();
  });

  it('shows a page error with the Request ID when the plan fails', async () => {
    server.use(
      repsOk(),
      http.get(`${INTEL}/intelligence/beat-plan`, () =>
        HttpResponse.json(
          { error: { code: 'UNKNOWN_ERROR', message: 'Boom', request_id: 'req-bp' } },
          { status: 500 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<BeatPlanPage />);

    const select = await screen.findByLabelText('Sales rep');
    await screen.findByRole('option', { name: 'ravi@adagen.in' });
    await user.selectOptions(select, 'rep-1');

    expect(await screen.findByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText(/Request ID: req-bp/)).toBeInTheDocument();
  });
});
