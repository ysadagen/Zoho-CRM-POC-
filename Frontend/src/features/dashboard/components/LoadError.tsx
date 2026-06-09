import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { ApiError } from '@/lib/api/errors';

export interface LoadErrorProps {
  error: unknown;
  onRetry: () => void;
  title?: string;
}

/**
 * In-card error state for a failed read query. Surfaces the Request ID so a
 * user complaint correlates to a server log line (CLAUDE.md §5.6 / §5.8) and
 * offers a Retry. (Mutations use the toast surface; this is read-only.)
 */
export function LoadError({ error, onRetry, title }: LoadErrorProps): JSX.Element {
  const apiError = error instanceof ApiError ? error : null;
  return (
    <div className="empty">
      <div className="ill">
        <Icon name="alertTriangle" size={28} />
      </div>
      <div className="ttl">{title ?? "Couldn't load this section"}</div>
      <div className="sub">{apiError?.message ?? 'Something went wrong. Please try again.'}</div>
      {apiError && (
        <div className="mono fs-12 text-muted mb-16">Request ID: {apiError.requestId}</div>
      )}
      <Button variant="sec" size="sm" icon="refresh" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}
