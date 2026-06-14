import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ApiError } from '@/lib/api/errors';

export interface PageErrorProps {
  error: unknown;
  onRetry: () => void;
}

/** Full-width read-error card with the Request ID + a Retry (UI_SPEC §5.8). */
export function PageError({ error, onRetry }: PageErrorProps): JSX.Element {
  const apiError = error instanceof ApiError ? error : null;
  return (
    <div className="card card-pad">
      <EmptyState
        icon="alertTriangle"
        title="Something went wrong"
        sub={apiError?.message ?? 'Please try again in a moment.'}
        action={
          <div className="flex col items-center gap-8">
            {apiError && (
              <div className="mono fs-12 text-muted">Request ID: {apiError.requestId}</div>
            )}
            <Button variant="sec" icon="refresh" onClick={onRetry}>
              Retry
            </Button>
          </div>
        }
      />
    </div>
  );
}
