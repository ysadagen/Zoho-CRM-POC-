import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';

import { AuthProvider } from '@/auth/AuthProvider';
import { ErrorBoundary } from '@/components/errors/ErrorBoundary';
import { ToastProvider } from '@/components/toast/ToastProvider';

import { AppRouter } from './router';

/**
 * Composition root: provider tree + router.
 *
 * - ErrorBoundary is outermost so a render crash anywhere shows a recoverable
 *   fallback instead of a blank screen.
 * - React Query owns server state (read queries retry twice; mutations never
 *   retry — see `CLAUDE.md §6`).
 * - AuthProvider owns the session; ToastProvider owns transient notifications
 *   (and the §5.6 Request-ID surface).
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 2, refetchOnWindowFocus: false, staleTime: 30_000 },
    mutations: { retry: 0 },
  },
});

export function App(): JSX.Element {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <AuthProvider>
            <ToastProvider>
              <AppRouter />
            </ToastProvider>
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
