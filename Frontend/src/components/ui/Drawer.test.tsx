import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { Drawer } from './Drawer';

describe('Drawer', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <Drawer open={false} onClose={() => {}} title="Edit">
        body
      </Drawer>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders a modal dialog with title, body and footer when open', () => {
    render(
      <Drawer open onClose={() => {}} title="Add Item" footer={<button>Save</button>}>
        <p>form here</p>
      </Drawer>,
    );
    const dialog = screen.getByRole('dialog', { name: 'Add Item' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByText('form here')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument();
  });

  it('closes on the close button, scrim click and Escape', async () => {
    const onClose = vi.fn();
    const { container } = render(
      <Drawer open onClose={onClose} title="Edit">
        body
      </Drawer>,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    await userEvent.click(container.querySelector('.scrim') as HTMLElement);
    await userEvent.keyboard('{Escape}');

    expect(onClose).toHaveBeenCalledTimes(3);
  });
});
