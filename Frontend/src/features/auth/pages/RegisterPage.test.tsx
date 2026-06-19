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

async function fillForm(user: ReturnType<typeof userEvent.setup>, confirm: string) {
  await user.type(screen.getByLabelText('Full name'), 'Ravi Menon');
  await user.type(screen.getByLabelText('Work email'), 'ravi@adagen.in');
  await user.type(screen.getByLabelText('Password'), 'secret123');
  await user.type(screen.getByLabelText('Confirm password'), confirm);
  await user.click(screen.getByRole('button', { name: /create account/i }));
}

describe('RegisterPage', () => {
  it('registers, auto-logs-in, and lands on the dashboard', async () => {
    server.use(
      http.post(`${BASE}/register`, () => HttpResponse.json(TEST_USER, { status: 201 })),
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
    renderWithProviders(<AppRouter />, { route: '/register' });

    await fillForm(user, 'secret123');

    expect(await screen.findByText(/Good (morning|afternoon|evening), Ravi/)).toBeInTheDocument();
  });

  it('flags a password mismatch without calling the API', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/register' });

    await fillForm(user, 'different');

    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument();
  });

  it('surfaces a duplicate-email error on the email field', async () => {
    server.use(
      http.post(`${BASE}/register`, () =>
        HttpResponse.json(
          { error: { code: 'EMAIL_ALREADY_REGISTERED', message: 'taken', request_id: 'r' } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<AppRouter />, { route: '/register' });

    await fillForm(user, 'secret123');

    expect(await screen.findByText('This email is already registered.')).toBeInTheDocument();
  });
});
