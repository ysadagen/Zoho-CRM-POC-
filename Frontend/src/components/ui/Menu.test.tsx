import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import { Menu, MenuItem, MenuLinkItem } from './Menu';

function renderMenu(onSelect = vi.fn()) {
  render(
    <MemoryRouter>
      <Menu triggerLabel="New Order" triggerIcon="plus" ariaLabel="New order">
        <MenuLinkItem to="/sales-orders/new" icon="bag">
          New Sales Order
        </MenuLinkItem>
        <MenuItem icon="cart" onSelect={onSelect}>
          New Purchase Order
        </MenuItem>
      </Menu>
    </MemoryRouter>,
  );
  return { onSelect };
}

describe('Menu', () => {
  it('is collapsed until the trigger is clicked', async () => {
    renderMenu();
    const trigger = screen.getByRole('button', { name: 'New order' });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();

    await userEvent.click(trigger);

    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('menu')).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'New Sales Order' })).toBeInTheDocument();
  });

  it('points a link item at its route', async () => {
    renderMenu();
    await userEvent.click(screen.getByRole('button', { name: 'New order' }));
    expect(screen.getByRole('menuitem', { name: 'New Sales Order' })).toHaveAttribute(
      'href',
      '/sales-orders/new',
    );
  });

  it('runs onSelect and closes when a button item is chosen', async () => {
    const { onSelect } = renderMenu();
    await userEvent.click(screen.getByRole('button', { name: 'New order' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'New Purchase Order' }));

    expect(onSelect).toHaveBeenCalledOnce();
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('closes on Escape', async () => {
    renderMenu();
    await userEvent.click(screen.getByRole('button', { name: 'New order' }));
    expect(screen.getByRole('menu')).toBeInTheDocument();

    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('closes on outside click', async () => {
    renderMenu();
    await userEvent.click(screen.getByRole('button', { name: 'New order' }));
    // The backdrop is the click-catcher behind the popup.
    await userEvent.click(document.querySelector('.menu-backdrop') as HTMLElement);
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });
});
