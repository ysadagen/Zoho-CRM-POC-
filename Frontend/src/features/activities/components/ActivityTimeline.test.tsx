import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { renderWithProviders } from '@/test/utils';
import type { Activity } from '@/types/api.types';

import { ActivityTimeline } from './ActivityTimeline';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const ACTIVITY: Activity = {
  id: 'a-1',
  type: 'CALL',
  rep_user_id: 'u-1',
  customer_id: 'c1',
  lead_id: null,
  occurred_at: '2026-06-17T10:30:00Z',
  duration_minutes: 30,
  remarks: 'Discussed pricing',
  created_by_user_id: 'u-1',
  created_at: '2026-06-17T10:35:00Z',
};

describe('ActivityTimeline', () => {
  it('renders activities from the API', async () => {
    server.use(
      http.get(`${BASE}/activities`, () =>
        HttpResponse.json({ items: [ACTIVITY], total: 1, limit: 50, offset: 0 }),
      ),
    );
    renderWithProviders(<ActivityTimeline customerId="c1" />);

    expect(await screen.findByText('Call')).toBeInTheDocument();
    expect(screen.getByText('Discussed pricing')).toBeInTheDocument();
    expect(screen.getByText('30 min')).toBeInTheDocument();
  });

  it('shows the empty state when there are no activities', async () => {
    server.use(
      http.get(`${BASE}/activities`, () =>
        HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 }),
      ),
    );
    renderWithProviders(<ActivityTimeline customerId="c1" />);

    expect(await screen.findByText('No activities yet')).toBeInTheDocument();
  });
});
