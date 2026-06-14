import { describe, it, expect, afterEach, vi } from 'vitest';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

async function loadEnv() {
  vi.resetModules();
  return (await import('./env')).env;
}

describe('env', () => {
  it('defaults the API base URL when unset', async () => {
    vi.stubEnv('VITE_API_BASE_URL', '');
    const env = await loadEnv();
    expect(env.apiBaseUrl).toBe('http://localhost:8000');
  });

  it('strips a trailing slash from the API base URL', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com/');
    const env = await loadEnv();
    expect(env.apiBaseUrl).toBe('https://api.example.com');
  });

  it('defaults appEnv to "dev" for an invalid value', async () => {
    vi.stubEnv('VITE_APP_ENV', 'bogus');
    const env = await loadEnv();
    expect(env.appEnv).toBe('dev');
  });

  it('accepts a valid appEnv', async () => {
    vi.stubEnv('VITE_APP_ENV', 'staging');
    const env = await loadEnv();
    expect(env.appEnv).toBe('staging');
  });
});
