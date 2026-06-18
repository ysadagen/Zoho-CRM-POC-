import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { setupServer } from 'msw/node';

import { clearSession, setSession } from '@/auth/token-storage';
import { TEST_USER } from '@/test/utils';
import { dashboardHandlers } from '@/test/dashboardHandlers';

import { App } from './App';

const server = setupServer(...dashboardHandlers);

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
