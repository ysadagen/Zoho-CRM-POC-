import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { TeamPerformancePage } from './TeamPerformancePage';

const BASE = 'http://localhost:8002/api/v1/intelligence';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const COHORT = {
  items: [
    {
      rep_user_id: 'u-1',
      rep_email: 'ravi@adagen.in',
      period_start: '2026-05-01',
      period_end: '2026-05-31',
      activity_counts: { visits: 10, meetings: 4, follow_ups: 6, calls: 12, hours_logged: 38 },
      effort_raw: 70,
      effort_score: 80,
      efficiency_components: {
        stage_change_rate: 70,
        won_rate: 65,
        revenue_efficiency: 72,
        time_to_close: 55,
        lead_score_utilization: 60,
      },
      efficiency_score: 75,
      efficiency_band: 'High',
      quadrant: 'HIGH_EFFORT_HIGH_EFFICIENCY',
    },
  ],
  total: 1,
  period_start: '2026-05-01',
  period_end: '2026-05-31',
};

function cohortOk() {
  return http.get(`${BASE}/effort-efficiency`, () => HttpResponse.json(COHORT));
}

describe('TeamPerformancePage', () => {
  it('renders the cohort with rep email and quadrant', async () => {
    server.use(cohortOk());
    renderWithProviders(<TeamPerformancePage />);
    expect(await screen.findAllByText('ravi@adagen.in')).not.toHaveLength(0);
    expect(screen.getByText('High effort · High efficiency')).toBeInTheDocument();
  });

  it('shows a page error with the Request ID on failure', async () => {
    server.use(
      http.get(`${BASE}/effort-efficiency`, () =>
        HttpResponse.json(
          { error: { code: 'UNKNOWN_ERROR', message: 'Boom', request_id: 'req-tp' } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<TeamPerformancePage />);
    expect(await screen.findByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText(/Request ID: req-tp/)).toBeInTheDocument();
  });
});
