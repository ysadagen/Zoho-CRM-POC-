import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ToastProvider } from './ToastProvider';
import { useToast } from './useToast';

function Trigger() {
  const toast = useToast();
  return (
    <div>
      <button onClick={() => toast.success('Saved')}>ok</button>
      <button
        onClick={() => toast.danger('Failed to save.', { requestId: 'req-789' })}
      >
        fail
      </button>
      <button
        onClick={() =>
          toast.danger('Out of stock', {
            requestId: 'req-stock',
            action: { label: 'Refresh stock', onClick: () => actionSpy() },
          })
        }
      >
        action
      </button>
    </div>
  );
}

const actionSpy = vi.fn();

afterEach(() => {
  vi.useRealTimers();
  actionSpy.mockReset();
});

function renderWithToast() {
  return render(
    <ToastProvider>
      <Trigger />
    </ToastProvider>,
  );
}

describe('toast', () => {
  it('useToast throws outside a provider', () => {
    function Bare() {
      useToast();
      return null;
    }
    // Silence the expected React error boundary log for this assertion.
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Bare />)).toThrow(/useToast must be used within/);
    spy.mockRestore();
  });

  it('shows a success toast with its message', async () => {
    renderWithToast();
    await userEvent.click(screen.getByText('ok'));
    expect(await screen.findByText('Saved')).toBeInTheDocument();
  });

  it('renders the Request ID on a danger toast (§5.6 non-negotiable)', async () => {
    renderWithToast();
    await userEvent.click(screen.getByText('fail'));

    const toast = (await screen.findByText('Failed to save.')).closest('.toast');
    expect(toast).toHaveClass('danger');
    expect(toast).toHaveTextContent('Request ID: req-789');
    // The ID is rendered in the mono span the design reserves for it.
    expect(toast?.querySelector('.req .mono')?.textContent).toBe('req-789');
  });

  it('runs a toast action and then dismisses it', async () => {
    renderWithToast();
    await userEvent.click(screen.getByText('action'));

    await userEvent.click(await screen.findByRole('button', { name: 'Refresh stock' }));
    expect(actionSpy).toHaveBeenCalledOnce();
    expect(screen.queryByText('Out of stock')).not.toBeInTheDocument();
  });

  it('dismisses on the close button', async () => {
    renderWithToast();
    await userEvent.click(screen.getByText('ok'));
    await screen.findByText('Saved');

    await userEvent.click(screen.getByRole('button', { name: 'Dismiss notification' }));
    expect(screen.queryByText('Saved')).not.toBeInTheDocument();
  });

  it('auto-dismisses after the timeout', () => {
    // fireEvent (sync, no userEvent timer interplay) keeps fake timers clean.
    vi.useFakeTimers();
    renderWithToast();
    fireEvent.click(screen.getByText('ok'));
    expect(screen.getByText('Saved')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(4_500);
    });
    expect(screen.queryByText('Saved')).not.toBeInTheDocument();
  });
});
