import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';

import { logger } from '@/lib/logger';

import { ErrorBoundary } from './ErrorBoundary';

function Boom(): JSX.Element {
  throw new Error('kaboom');
}

afterEach(() => vi.restoreAllMocks());

describe('ErrorBoundary', () => {
  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <div>all good</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText('all good')).toBeInTheDocument();
  });

  it('renders the fallback and logs the crash when a child throws', () => {
    const logSpy = vi.spyOn(logger, 'error').mockImplementation(() => {});
    // React logs the caught error to console.error — silence it for a clean run.
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reload page/i })).toBeInTheDocument();
    expect(logSpy).toHaveBeenCalledWith('ui.crash', expect.objectContaining({ message: 'kaboom' }));

    consoleSpy.mockRestore();
  });
});
