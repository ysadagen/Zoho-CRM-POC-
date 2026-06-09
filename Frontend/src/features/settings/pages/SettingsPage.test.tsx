import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { clearSession } from '@/auth/token-storage';
import { renderWithProviders, seedSession, TEST_USER } from '@/test/utils';

import { SettingsPage } from './SettingsPage';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => {
  server.resetHandlers();
  clearSession();
});
afterAll(() => server.close());

describe('SettingsPage', () => {
  it('shows the profile and a disabled password placeholder', () => {
    seedSession();
    renderWithProviders(<SettingsPage />);

    expect(screen.getByText(TEST_USER.full_name)).toBeInTheDocument();
    expect(screen.getByText(TEST_USER.email)).toBeInTheDocument();
    expect(screen.getByText('Operations')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Change password' })).toBeDisabled();
  });

  it('edits the name and reflects it on the profile', async () => {
    server.use(
      http.patch(`${BASE}/users/${TEST_USER.id}`, () =>
        HttpResponse.json({ ...TEST_USER, full_name: 'Ravi Kumar' }),
      ),
    );
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

    await user.click(screen.getByRole('button', { name: 'Edit name' }));
    const name = await screen.findByLabelText('Full name');
    await user.clear(name);
    await user.type(name, 'Ravi Kumar');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Name updated.')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Ravi Kumar')).toBeInTheDocument());
  });

  it('validates a required name', async () => {
    seedSession();
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

    await user.click(screen.getByRole('button', { name: 'Edit name' }));
    await user.clear(await screen.findByLabelText('Full name'));
    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Name is required')).toBeInTheDocument();
  });
});
