import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { getBeatPlan, listReps } from './beatPlan.api';

const BACKEND = 'http://localhost:8000/api/v1';
const INTEL = 'http://localhost:8002/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('beatPlan.api', () => {
  it('getBeatPlan hits the Intelligence endpoint with rep + max_visits params', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${INTEL}/intelligence/beat-plan`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({
          rep_user_id: 'rep-1',
          generated_at: '2026-06-18T00:00:00Z',
          max_visits: 5,
          clusters: [],
          suggested_beat: [],
          all_customers: [],
        });
      }),
    );

    const plan = await getBeatPlan({ rep_user_id: 'rep-1', max_visits: 5 });
    expect(plan.rep_user_id).toBe('rep-1');
    expect(url?.searchParams.get('rep_user_id')).toBe('rep-1');
    expect(url?.searchParams.get('max_visits')).toBe('5');
  });

  it('listReps hits the Backend users endpoint with limit 100', async () => {
    let url: URL | undefined;
    server.use(
      http.get(`${BACKEND}/users`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, limit: 100, offset: 0 });
      }),
    );

    await listReps();
    expect(url?.searchParams.get('limit')).toBe('100');
  });
});
