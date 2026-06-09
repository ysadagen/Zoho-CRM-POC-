import { cx } from '@/lib/cx';

export interface AuthAlertProps {
  tone: 'info' | 'danger';
  message: string;
  /** Shown on danger alerts so a failure correlates to a server log line (§5.6). */
  requestId?: string;
}

export function AuthAlert({ tone, message, requestId }: AuthAlertProps): JSX.Element {
  return (
    <div className={cx('auth-alert', tone)} role={tone === 'danger' ? 'alert' : 'status'}>
      <div>{message}</div>
      {requestId && (
        <div className="req">
          Request ID: <span className="mono">{requestId}</span>
        </div>
      )}
    </div>
  );
}
