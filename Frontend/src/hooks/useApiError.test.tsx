import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ToastProvider } from '@/components/toast/ToastProvider';
import { ApiError } from '@/lib/api/errors';
import { logger } from '@/lib/logger';

import { useApiError } from './useApiError';

function Trigger({ error, opts }: { error: unknown; opts?: Parameters<ReturnType<typeof useApiError>>[1] }) {
  const report = useApiError();
  return <button onClick={() => report(error, opts)}>go</button>;
}

function renderWith(error: unknown, opts?: Parameters<ReturnType<typeof useApiError>>[1]) {
  return render(
    <ToastProvider>
      <Trigger error={error} opts={opts} />
    </ToastProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe('useApiError', () => {
  it('shows a danger toast with the Request ID and logs the failure', async () => {
    const logSpy = vi.spyOn(logger, 'error').mockImplementation(() => {});
    const error = new ApiError({
      code: 'DUPLICATE_SKU',
      message: 'SKU already exists',
      httpStatus: 409,
      requestId: 'req-42',
    });
    renderWith(error, { scope: 'items.create' });

    await userEvent.click(screen.getByText('go'));

    const toast = (await screen.findByText('SKU already exists')).closest('.toast');
    expect(toast).toHaveClass('danger');
    expect(toast).toHaveTextContent('Request ID: req-42');
    expect(logSpy).toHaveBeenCalledWith('items.create', {
      code: 'DUPLICATE_SKU',
      httpStatus: 409,
      requestId: 'req-42',
    });
  });

  it('falls back to a generic message for a non-ApiError', async () => {
    vi.spyOn(logger, 'error').mockImplementation(() => {});
    renderWith(new Error('boom'), { fallbackMessage: 'Could not save the item.' });

    await userEvent.click(screen.getByText('go'));
    expect(await screen.findByText('Could not save the item.')).toBeInTheDocument();
  });

  it('attaches a recovery action to the toast', async () => {
    vi.spyOn(logger, 'error').mockImplementation(() => {});
    const onClick = vi.fn();
    const error = new ApiError({
      code: 'INSUFFICIENT_STOCK',
      message: 'Not enough stock',
      httpStatus: 409,
      requestId: 'req-9',
    });
    renderWith(error, { action: { label: 'Refresh stock', onClick } });

    await userEvent.click(screen.getByText('go'));
    await userEvent.click(await screen.findByRole('button', { name: 'Refresh stock' }));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
