import { useCallback } from 'react';

import type { ToastAction } from '@/components/toast/ToastContext';
import { useToast } from '@/components/toast/useToast';
import { ApiError } from '@/lib/api/errors';
import { logger } from '@/lib/logger';

export interface ReportErrorOptions {
  /** Log scope identifying the operation, e.g. "items.create". */
  scope?: string;
  /** Shown when the error isn't an ApiError (network glitch, thrown string). */
  fallbackMessage?: string;
  /** Inline recovery action on the toast (e.g. "Refresh stock"). */
  action?: ToastAction;
}

export type ReportApiError = (error: unknown, opts?: ReportErrorOptions) => void;

/**
 * Canonical error surface for mutations / actions: logs the failure with its
 * server code + Request ID (correlates to a Backend log line) and raises a
 * danger toast carrying that Request ID (§5.6). Read-query errors use inline
 * page/card error states instead.
 */
export function useApiError(): ReportApiError {
  const toast = useToast();

  return useCallback(
    (error, opts) => {
      const apiError = error instanceof ApiError ? error : null;
      const message =
        apiError?.message ?? opts?.fallbackMessage ?? 'Something went wrong. Please try again.';
      const requestId = apiError?.requestId;

      logger.error(opts?.scope ?? 'api.error', {
        code: apiError?.code ?? 'UNKNOWN_ERROR',
        httpStatus: apiError?.httpStatus,
        requestId,
      });

      toast.danger(message, {
        requestId,
        action: opts?.action,
        persist: Boolean(opts?.action),
      });
    },
    [toast],
  );
}
