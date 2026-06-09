import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { login, register } from './auth.api';

const BASE = 'http://localhost:8000/api/v1/auth';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('auth.api', () => {
  it('login posts credentials and returns the token payload', async () => {
    let captured: unknown;
    server.use(
      http.post(`${BASE}/login`, async ({ request }) => {
        captured = await request.json();
        return HttpResponse.json({
          access_token: 'tok',
          token_type: 'bearer',
          expires_in: 3600,
          user: { id: 'u1' },
        });
      }),
    );

    const res = await login({ email: 'a@b.com', password: 'pw' });
    expect(captured).toMatchObject({ email: 'a@b.com', password: 'pw' });
    expect(res.access_token).toBe('tok');
    expect(res.expires_in).toBe(3600);
  });

  it('register posts the new-user fields and returns the created user', async () => {
    let captured: unknown;
    server.use(
      http.post(`${BASE}/register`, async ({ request }) => {
        captured = await request.json();
        return HttpResponse.json(
          { id: 'u2', email: 'c@d.com', full_name: 'C D' },
          { status: 201 },
        );
      }),
    );

    const user = await register({ email: 'c@d.com', full_name: 'C D', password: 'longenough' });
    expect(captured).toMatchObject({ email: 'c@d.com', full_name: 'C D', password: 'longenough' });
    expect(user.id).toBe('u2');
  });
});
