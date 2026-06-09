import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { clearSession, setSession } from '@/auth/token-storage';
import { TEST_USER } from '@/test/utils';

import { App } from './App';

const BASE = 'http://localhost:8000/api/v1';
const emptyList = () => HttpResponse.json({ items: [], total: 0, limit: 100, offset: 0 });

const server = setupServer(
  http.get(`${BASE}/items`, emptyList),
  http.get(`${BASE}/stock-movements`, emptyList),
  http.get(`${BASE}/purchase-orders`, emptyList),
  http.get(`${BASE}/sales-orders`, emptyList),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => {
  server.resetHandlers();
  clearSession();
  window.history.pushState({}, '', '/');
});
afterAll(() => server.close());

describe('App', () => {
  it('renders the dashboard for an authenticated session', async () => {
    setSession({ token: 't', expiresAt: Date.now() + 3_600_000, user: TEST_USER });
    render(<App />);

    expect(await screen.findByText(/Good (morning|afternoon|evening), Ravi/)).toBeInTheDocument();
    expect(await screen.findByText('Total Stock Value')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
  });
});
