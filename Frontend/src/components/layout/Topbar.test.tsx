import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';

import { AppRouter } from '@/app/router';
import { clearSession } from '@/auth/token-storage';
import { renderWithProviders, seedSession } from '@/test/utils';
import { dashboardHandlers } from '@/test/dashboardHandlers';

// The dashboard (the route under test) fires these read queries on mount.
const server = setupServer(...dashboardHandlers);

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
