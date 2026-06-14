import { describe, it, expect, vi, beforeEach, beforeAll, afterEach, afterAll } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

// Force dev mode so the `env.isDev`-gated debug-logging branches in both the
// logger and the HTTP client actually execute (they are no-ops in test mode).
vi.mock('@/config/env', () => ({
  env: {
    apiBaseUrl: 'http://localhost:8000',
    appEnv: 'dev',
    mode: 'development',
    isDev: true,
    isProd: false,
  },
}));

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('debug logging in dev mode', () => {
  let debugSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {});
  });

  it('logger.debug emits when the threshold is debug', async () => {
    vi.resetModules();
    const { logger } = await import('@/lib/logger');
    logger.debug('dev.scope', { a: 1 });
    expect(debugSpy).toHaveBeenCalled();
  });

  it('the http client logs request and response debug lines', async () => {
    vi.resetModules();
    const { apiGet } = await import('@/lib/api/client');
    server.use(
      http.get('http://localhost:8000/api/v1/ping', () => HttpResponse.json({ ok: true })),
    );
    await apiGet('/api/v1/ping');
    expect(debugSpy).toHaveBeenCalled();
  });
});
