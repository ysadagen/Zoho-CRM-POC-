import { useEffect, type ReactNode } from 'react';

import { cx } from '@/lib/cx';

import { Button } from './Button';

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /** Sticky footer actions (e.g. Cancel / Save). */
  footer?: ReactNode;
}

/**
 * Right-side panel for create/edit forms (DESIGN_SYSTEM §6.8). Mounts only when
 * open — so the form inside resets on each open and tests aren't tripped up by
 * hidden content. ESC and a scrim click both close it.
 */
export function Drawer({ open, onClose, title, children, footer }: DrawerProps): JSX.Element | null {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      <div className={cx('scrim', 'open')} onClick={onClose} aria-hidden="true" />
      <aside className="drawer open" role="dialog" aria-modal="true" aria-label={title}>
        <div className="drawer-head">
          <h2>{title}</h2>
          <Button variant="ghost" iconOnly icon="close" aria-label="Close" onClick={onClose} />
        </div>
        <div className="drawer-body">{children}</div>
        {footer && <div className="drawer-foot">{footer}</div>}
      </aside>
    </>
  );
}
