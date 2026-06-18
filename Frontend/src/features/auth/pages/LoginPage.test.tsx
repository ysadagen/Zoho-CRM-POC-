import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { AppRouter } from '@/app/router';
import { clearSession } from '@/auth/token-storage';
import { renderWithProviders, TEST_USER } from '@/test/utils';
import { dashboardHandlers } from '@/test/dashboardHandlers';

const BASE = 'http://localhost:8000/api/v1/auth';

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  clearSession();
});
afterAll(() => server.close());

describe('LoginPage', () => {
  it('logs in and lands on the dashboard', async () => {
    server.use(
      http.post(`${BASE}/login`, () =>
        HttpResponse.json({
          access_token: 'tok',
          token_type: 'bearer',
          expires_in: 3600,
          user: TEST_USER,
        }),
      ),
      ...dashboardHandlers,
    );
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/login' });

    await user.type(screen.getByLabelText('Work email'), 'ravi@adagen.in');
    await user.type(screen.getByLabelText('Password'), 'secret123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText(/Good (morning|afternoon|evening), Ravi/)).toBeInTheDocument();
  });

  it('shows a vague inline error on invalid credentials', async () => {
    server.use(
      http.post(`${BASE}/login`, () =>
        HttpResponse.json(
          { error: { code: 'INVALID_CREDENTIALS', message: 'bad', request_id: 'r1' } },
          { status: 401 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/login' });

    await user.type(screen.getByLabelText('Work email'), 'ravi@adagen.in');
    await user.type(screen.getByLabelText('Password'), 'wrong');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText('Invalid email or password.')).toBeInTheDocument();
  });

  it('validates required fields before calling the API', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/login' });

    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText('Email is required')).toBeInTheDocument();
    expect(screen.getByText('Password is required')).toBeInTheDocument();
  });
});
