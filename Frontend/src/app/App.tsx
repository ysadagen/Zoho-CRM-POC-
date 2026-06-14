import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';

import { AuthProvider } from '@/auth/AuthProvider';
import { ErrorBoundary } from '@/components/errors/ErrorBoundary';
import { ToastProvider } from '@/components/toast/ToastProvider';

import { AppRouter } from './router';

/**
 * Composition root: provider tree + router.
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
