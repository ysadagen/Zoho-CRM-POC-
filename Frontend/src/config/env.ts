/**
 * Typed access to Vite env vars. The ONLY place `import.meta.env.*` is read.
 * Add a new env var here when you add it to `.env.example`.
 */

type AppEnv = 'dev' | 'staging' | 'prod';

function readString(key: string, fallback: string): string {
  const raw = (import.meta.env as Record<string, string | undefined>)[key];
  return raw && raw.length > 0 ? raw : fallback;
}

function readAppEnv(): AppEnv {
  const raw = readString('VITE_APP_ENV', 'dev');
  if (raw === 'dev' || raw === 'staging' || raw === 'prod') {
    return raw;
  }
  return 'dev';
}

export const env = {
  apiBaseUrl: readString('VITE_API_BASE_URL', 'http://localhost:8000').replace(/\/+$/, ''),
  appEnv: readAppEnv(),
  mode: import.meta.env.MODE as 'development' | 'production' | 'test',
  isDev: import.meta.env.MODE === 'development',
  isProd: import.meta.env.MODE === 'production',
} as const;

export type { AppEnv };
