import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { Modal } from './Modal';

describe('Modal', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <Modal open={false} onClose={() => {}} title="Confirm">
        body
      </Modal>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders a labelled dialog with body and footer when open', () => {
    render(
      <Modal open onClose={() => {}} title="Remove term" tone="danger" footer={<button>Confirm</button>}>
        <p>are you sure?</p>
      </Modal>,
    );
    const dialog = screen.getByRole('dialog', { name: 'Remove term' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByText('are you sure?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument();
  });

  it('closes on the close button and Escape', async () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Confirm">
        body
      </Modal>,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
