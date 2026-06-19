import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import { setupServer } from 'msw/node';

import { clearSession } from '@/auth/token-storage';
import { renderWithProviders, seedSession } from '@/test/utils';
import { dashboardHandlers } from '@/test/dashboardHandlers';

import { routes } from './routes';
import { AppRouter } from './router';

const server = setupServer(...dashboardHandlers);

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => {
  server.resetHandlers();
  clearSession();
});
afterAll(() => server.close());

describe('AppRouter', () => {
  it('redirects an unauthenticated user to the login page', async () => {
    renderWithProviders(<AppRouter />, { route: routes.dashboard });
    expect(await screen.findByText('Sign in to your workspace')).toBeInTheDocument();
  });

  it('redirects the index path to the dashboard when authenticated', async () => {
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/' });
    expect(
      await screen.findByText(/Good (morning|afternoon|evening), Ravi/),
    ).toBeInTheDocument();
  });

  it('renders the Settings page on its route', () => {
    seedSession();
    renderWithProviders(<AppRouter />, { route: routes.settings });
    expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument();
  });

  it('renders the 404 page for an unknown route when authenticated', () => {
    seedSession();
    renderWithProviders(<AppRouter />, { route: '/does-not-exist' });
    expect(screen.getByText('404 — nothing here')).toBeInTheDocument();
  });

  it('keeps the app chrome on every route', () => {
    seedSession();
    renderWithProviders(<AppRouter />, { route: routes.settings });
    expect(screen.getByRole('link', { name: 'Settings' })).toBeInTheDocument();
  });
});
