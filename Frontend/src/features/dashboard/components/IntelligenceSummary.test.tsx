import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';

import { IntelligenceSummary } from './IntelligenceSummary';

const BACKEND = 'http://localhost:8000/api/v1';
const INTEL = 'http://localhost:8002/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function handlers() {
  return [
    http.get(`${INTEL}/intelligence/lead-scores`, () =>
      HttpResponse.json({ items: [], total: 7, limit: 1, offset: 0 }),
    ),
    http.get(`${INTEL}/intelligence/customer-health`, () =>
      HttpResponse.json({
        items: [
          { classification: 'AT_RISK' },
          { classification: 'CRITICAL' },
          { classification: 'AT_RISK' },
          { classification: 'HEALTHY' },
        ],
        total: 4,
      }),
    ),
    http.get(`${BACKEND}/leads`, () =>
      HttpResponse.json({
        items: [
          { id: 'a', stage: 'NEW' },
          { id: 'b', stage: 'NEW' },
          { id: 'c', stage: 'WON' },
        ],
        total: 3,
        limit: 200,
        offset: 0,
      }),
    ),
  ];
}

describe('IntelligenceSummary', () => {
  it('shows the hot-lead count, at-risk count, and the lead funnel', async () => {
    server.use(...handlers());
    renderWithProviders(<IntelligenceSummary />);

    // Hot leads = total from the Intelligence lead-scores endpoint.
    expect(await screen.findByText('7')).toBeInTheDocument();
    // At-risk customers = AT_RISK + CRITICAL = 3 (counted client-side).
    expect(await screen.findByText('At-risk customers')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    // Funnel renders each stage label.
    expect(await screen.findByText('Negotiation')).toBeInTheDocument();
    expect(screen.getByText('New')).toBeInTheDocument();
  });
});
