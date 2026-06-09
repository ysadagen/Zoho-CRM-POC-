import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { AppRouter } from '@/app/router';
import { clearSession } from '@/auth/token-storage';
import { renderWithProviders, seedSession } from '@/test/utils';

const API = 'http://localhost:8000/api/v1';
const emptyList = () => HttpResponse.json({ items: [], total: 0, limit: 100, offset: 0 });

// The dashboard (the route under test) fires these read queries on mount.
const server = setupServer(
  http.get(`${API}/items`, emptyList),
  http.get(`${API}/stock-movements`, emptyList),
  http.get(`${API}/purchase-orders`, emptyList),
  http.get(`${API}/sales-orders`, emptyList),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => {
  server.resetHandlers();
  clearSession();
});
afterAll(() => server.close());

describe('Topbar account menu', () => {
  it('shows the signed-in user and logs out to the login page', async () => {
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/dashboard' });

    // The user's name is shown in the topbar.
    expect(await screen.findByText('Ravi Menon')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Account menu' }));
    await user.click(screen.getByRole('menuitem', { name: /log out/i }));

    expect(await screen.findByText('Sign in to your workspace')).toBeInTheDocument();
  });
});
