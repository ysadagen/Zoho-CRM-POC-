import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { updateProfile } from './settings.api';

const BASE = 'http://localhost:8000/api/v1';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('settings.api', () => {
  it('updateProfile PATCHes the user and returns the updated record', async () => {
    let body: unknown;
    server.use(
      http.patch(`${BASE}/users/u-1`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: 'u-1', full_name: 'Ravi K', email: 'ravi@adagen.in' });
      }),
    );

    const user = await updateProfile('u-1', { full_name: 'Ravi K' });
    expect(body).toEqual({ full_name: 'Ravi K' });
    expect(user.full_name).toBe('Ravi K');
  });
});
