import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { cx } from '@/lib/cx';

import { Icon, type IconName } from './Icon';

interface MenuContextValue {
  close: () => void;
}

const MenuContext = createContext<MenuContextValue | null>(null);

export interface MenuProps {
  /** Trigger button label (text or nodes). */
  triggerLabel: ReactNode;
  /** Accessible name for the trigger when the label isn't self-describing. */
  ariaLabel?: string;
  /** Class list for the trigger — defaults to a primary button. */
  triggerClassName?: string;
  /** Leading icon on the trigger. */
  triggerIcon?: IconName;
  /** Which edge the popup aligns to (default: right). */
  align?: 'left' | 'right';
  /** Menu items — compose with {@link MenuItem} / {@link MenuLinkItem}. */
  children: ReactNode;
}

/**
 * Accessible dropdown menu built on the design system's `.menu-*` classes.
 * Closes on outside click, on ESC, and after a child item is activated.
 */
export function Menu({
  triggerLabel,
  ariaLabel,
  triggerClassName = 'btn btn-pri',
  triggerIcon,
  align = 'right',
  children,
}: MenuProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const close = (): void => setOpen(false);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open]);

  return (
    <div className="menu-anchor">
      <button
        ref={triggerRef}
        type="button"
        className={triggerClassName}
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={ariaLabel}
      >
        {triggerIcon && <Icon name={triggerIcon} />}
        {triggerLabel}
        <Icon name="chevDown" />
      </button>

      {open && (
        <>
          <div className="menu-backdrop" onClick={close} />
          <div className={cx('menu-pop', align === 'left' && 'menu-pop-left')} role="menu">
            <MenuContext.Provider value={{ close }}>{children}</MenuContext.Provider>
          </div>
        </>
      )}
    </div>
  );
}

interface MenuItemBaseProps {
  icon?: IconName;
  children: ReactNode;
}

/** A `<button>` menu item — closes the menu, then runs `onSelect`. */
export function MenuItem({
  icon,
  children,
  onSelect,
  danger,
}: MenuItemBaseProps & { onSelect: () => void; danger?: boolean }): JSX.Element {
  const ctx = useContext(MenuContext);
  return (
    <button
      type="button"
      className={cx('menu-item', danger && 'danger')}
      role="menuitem"
      onClick={() => {
        ctx?.close();
        onSelect();
      }}
    >
      {icon && <Icon name={icon} size={14} />}
      {children}
    </button>
  );
}

/** A router-`<Link>` menu item — closes the menu on navigate. */
export function MenuLinkItem({
  icon,
  children,
  to,
}: MenuItemBaseProps & { to: string }): JSX.Element {
  const ctx = useContext(MenuContext);
  return (
    <Link className="menu-item" role="menuitem" to={to} onClick={() => ctx?.close()}>
      {icon && <Icon name={icon} size={14} />}
      {children}
    </Link>
  );
}
