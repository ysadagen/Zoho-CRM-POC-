import { describe, it, expect, beforeAll, afterAll, afterEach, vi } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import {
  apiGet,
  apiPost,
  apiPatch,
  apiDelete,
  configureAuthTokenSource,
  configureAuthFailureHandler,
} from './client';
import { ApiError } from './errors';

const BASE = 'http://localhost:8000';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  configureAuthTokenSource(() => null);
  configureAuthFailureHandler(() => {});
});
afterAll(() => server.close());

describe('httpClient interceptors', () => {
  it('attaches an X-Request-ID header to every request', async () => {
    let seen: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/ping`, ({ request }) => {
        seen = request.headers.get('x-request-id');
        return HttpResponse.json({ ok: true });
      }),
    );
    await apiGet('/api/v1/ping');
    expect(seen).toBeTruthy();
  });

  it('attaches a Bearer token when a token source is configured', async () => {
    configureAuthTokenSource(() => 'tok-123');
    let auth: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/me`, ({ request }) => {
        auth = request.headers.get('authorization');
        return HttpResponse.json({ ok: true });
      }),
    );
    await apiGet('/api/v1/me');
    expect(auth).toBe('Bearer tok-123');
  });

  it('apiPatch returns the response body', async () => {
    server.use(
      http.patch(`${BASE}/api/v1/items/1`, () => HttpResponse.json({ id: '1', name: 'X' })),
    );
    await expect(apiPatch('/api/v1/items/1', { name: 'X' })).resolves.toEqual({
      id: '1',
      name: 'X',
    });
  });

  it('apiDelete returns the response body', async () => {
    server.use(http.delete(`${BASE}/api/v1/items/1`, () => HttpResponse.json({ ok: true })));
    await expect(apiDelete('/api/v1/items/1')).resolves.toEqual({ ok: true });
  });

  it('normalizes a Backend error envelope to ApiError', async () => {
    server.use(
      http.get(`${BASE}/api/v1/items`, () =>
        HttpResponse.json(
          { error: { code: 'ITEM_NOT_FOUND', message: 'nope', request_id: 'req-5' } },
          { status: 404 },
        ),
      ),
    );
    await expect(apiGet('/api/v1/items')).rejects.toMatchObject({
      code: 'ITEM_NOT_FOUND',
      requestId: 'req-5',
      httpStatus: 404,
    });
  });

  it('fires the auth-failure handler on a 401 auth-failure code', async () => {
    const onFail = vi.fn();
    configureAuthFailureHandler(onFail);
    server.use(
      http.get(`${BASE}/api/v1/secure`, () =>
        HttpResponse.json(
          { error: { code: 'EXPIRED_TOKEN', message: 'expired', request_id: 'r' } },
          { status: 401 },
        ),
      ),
    );
    await expect(apiGet('/api/v1/secure')).rejects.toBeInstanceOf(ApiError);
    expect(onFail).toHaveBeenCalledOnce();
  });

  it('does NOT fire the handler for an auth-flow path (login is exempt)', async () => {
    const onFail = vi.fn();
    configureAuthFailureHandler(onFail);
    // EXPIRED_TOKEN is an auth-failure code, but on /auth/login it must be
    // treated as a normal failed-login flow, not a session expiry.
    server.use(
      http.post(`${BASE}/api/v1/auth/login`, () =>
        HttpResponse.json(
          { error: { code: 'EXPIRED_TOKEN', message: 'x', request_id: 'r' } },
          { status: 401 },
        ),
      ),
    );
    await expect(apiPost('/api/v1/auth/login', {})).rejects.toBeInstanceOf(ApiError);
    expect(onFail).not.toHaveBeenCalled();
  });
});
