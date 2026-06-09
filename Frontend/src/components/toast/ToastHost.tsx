import { Icon, type IconName } from '@/components/ui/Icon';

import type { Toast, ToastVariant } from './ToastContext';

const ICON_FOR: Record<ToastVariant, IconName> = {
  success: 'check',
  info: 'info',
  warn: 'alertTriangle',
  danger: 'alertTriangle',
};

export interface ToastHostProps {
  toasts: Toast[];
  onDismiss: (id: string) => void;
}

/** Renders the bottom-right toast stack. Pure presentational. */
export function ToastHost({ toasts, onDismiss }: ToastHostProps): JSX.Element {
  return (
    <div className="toasts" role="region" aria-live="polite" aria-label="Notifications">
      {toasts.map((toast) => {
        const action = toast.action;
        return (
          <div key={toast.id} className={`toast ${toast.variant}`} role="status">
            <span className="ic">
              <Icon name={ICON_FOR[toast.variant]} size={13} />
            </span>
            <div className="body">
              <span>{toast.message}</span>
              {toast.requestId && (
                <span className="req">
                  Request ID: <span className="mono">{toast.requestId}</span>
                </span>
              )}
            </div>
            {action && (
              <button
                type="button"
                className="toast-action"
                onClick={() => {
                  action.onClick();
                  onDismiss(toast.id);
                }}
              >
                {action.label}
              </button>
            )}
            <button
              type="button"
              className="x"
              aria-label="Dismiss notification"
              onClick={() => onDismiss(toast.id)}
            >
              <Icon name="close" size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
