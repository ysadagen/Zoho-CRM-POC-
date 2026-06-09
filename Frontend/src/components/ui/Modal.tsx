import { useEffect, type ReactNode } from 'react';

import { cx } from '@/lib/cx';

import { Icon } from './Icon';

export type ModalTone = 'default' | 'danger' | 'success';

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  sub?: string;
  tone?: ModalTone;
  children: ReactNode;
  /** Footer action buttons (e.g. Cancel / Confirm). */
  footer?: ReactNode;
}

/**
 * Centred confirmation / quick-form dialog (DESIGN_SYSTEM §6.9). Mounts only
 * while open; ESC and a backdrop click close it.
 */
export function Modal({
  open,
  onClose,
  title,
  sub,
  tone = 'default',
  children,
  footer,
}: ModalProps): JSX.Element | null {
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
    <div className="modal-host open" onClick={onClose}>
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="head">
          {tone !== 'default' && (
            <span className={cx('ic', tone)}>
              <Icon name={tone === 'danger' ? 'alertTriangle' : 'check'} size={16} />
            </span>
          )}
          <div>
            <h2>{title}</h2>
            {sub && <div className="sub">{sub}</div>}
          </div>
          <button type="button" className="x" aria-label="Close" onClick={onClose}>
            <Icon name="close" size={16} />
          </button>
        </div>
        <div className="body">{children}</div>
        {footer && <div className="foot">{footer}</div>}
      </div>
    </div>
  );
}
