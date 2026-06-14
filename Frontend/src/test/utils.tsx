import type { ReactElement } from 'react';
import { render, type RenderResult } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

import { AuthProvider } from '@/auth/AuthProvider';
import { ToastProvider } from '@/components/toast/ToastProvider';
import { setSession } from '@/auth/token-storage';
import type { User } from '@/types/api.types';

export const TEST_USER: User = {
  id: 'u-1',
  email: 'ravi@adagen.in',
  full_name: 'Ravi Menon',
  is_admin: false,
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

/** Seed a valid (non-expired) session so protected routes render. */
export function seedSession(user: User = TEST_USER): void {
  setSession({ token: 'test-token', expiresAt: Date.now() + 3_600_000, user });
}

/** Render a tree inside the real provider stack at a given route. */
export function renderWithProviders(
  ui: ReactElement,
  { route = '/', state }: { route?: string; state?: unknown } = {},
): RenderResult {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const initialEntry = state === undefined ? route : { pathname: route, state };
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter
        initialEntries={[initialEntry]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <AuthProvider>
          <ToastProvider>{ui}</ToastProvider>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
