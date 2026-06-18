import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { getLeadScore, listLeadScores, listLeads } from './leads.api';

const BACKEND = 'http://localhost:8000/api/v1';
const INTEL = 'http://localhost:8002/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('leads.api', () => {
  it('lists leads from the Backend', async () => {
    server.use(
      http.get(`${BACKEND}/leads`, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('stage')).toBe('NEW');
        return HttpResponse.json({ items: [], total: 0, limit: 25, offset: 0 });
      }),
    );
    const res = await listLeads({ limit: 25, offset: 0, stage: 'NEW' });
    expect(res.total).toBe(0);
  });

  it('reads lead scores from the Intelligence service (port 8002)', async () => {
    server.use(
      http.get(`${INTEL}/intelligence/lead-scores`, () =>
        HttpResponse.json({ items: [], total: 0, limit: 100, offset: 0 }),
      ),
    );
    const res = await listLeadScores();
    expect(res.items).toEqual([]);
  });

  it('reads a single lead score from the Intelligence service', async () => {
    server.use(
      http.get(`${INTEL}/intelligence/lead-scores/l1`, () =>
        HttpResponse.json({
          lead_id: 'l1',
          config_version: 1,
          computed_at: '2026-06-18T00:00:00Z',
          components: { urgency: 70, location: 50, contribution_margin: 70, quantity: 100, product_margin: 60 },
          total_score: 70,
          classification: 'MEDIUM',
          defaults_applied: [],
          history: [],
        }),
      ),
    );
    const res = await getLeadScore('l1');
    expect(res.classification).toBe('MEDIUM');
    expect(res.history).toEqual([]);
  });
});
