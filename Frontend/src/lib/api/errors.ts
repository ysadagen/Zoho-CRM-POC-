/**
 * Normalised API error surface.
 *
 * Components catch `ApiError` — not `AxiosError`. The response interceptor in
 * `client.ts` is the only place that constructs an `ApiError`.
 *
 * Stable codes mirror `Backend/docs/Backend_Reference.md` §5.
 */

import type { AxiosError } from 'axios';

import type { ApiErrorEnvelope } from '@/types/api.types';

import { REQUEST_ID_HEADER } from './request-id';

export type ErrorCode =
  | 'ADMIN_REQUIRED'
  | 'CANNOT_DEACTIVATE_SELF'
  | 'CUSTOMER_NOT_FOUND'
  | 'DUPLICATE_CUSTOMER'
  | 'DUPLICATE_LINE_ITEM'
  | 'DUPLICATE_PURCHASE_ORDER'
  | 'DUPLICATE_SALES_ORDER'
  | 'DUPLICATE_SKU'
  | 'DUPLICATE_TERM'
  | 'DUPLICATE_VENDOR'
  | 'EMAIL_ALREADY_REGISTERED'
  | 'EXPIRED_TOKEN'
  | 'INSUFFICIENT_STOCK'
  | 'INVALID_CREDENTIALS'
  | 'INVALID_DATE_RANGE'
  | 'INVALID_REFERENCE_PAIR'
  | 'INVALID_TOKEN'
  | 'ITEM_NOT_FOUND'
  | 'MISSING_TOKEN'
  | 'NETWORK_ERROR'
  | 'OVERLAPPING_TERMS'
  | 'PO_NOT_DRAFT'
  | 'PRICE_UNAVAILABLE'
  | 'PURCHASE_ORDER_NOT_FOUND'
  | 'SALES_ORDER_NOT_FOUND'
  | 'SO_NOT_DRAFT'
  | 'TERM_NOT_FOUND'
  | 'UNKNOWN_ERROR'
  | 'USER_NOT_FOUND'
  | 'VALIDATION_ERROR'
  | 'VENDOR_NOT_FOUND';

export interface ApiErrorOptions {
  code: ErrorCode | string;
  message: string;
  httpStatus: number;
  requestId: string;
  field?: string;
  details?: unknown;
}

export class ApiError extends Error {
  public readonly code: ErrorCode | string;
  public readonly httpStatus: number;
  public readonly requestId: string;
  public readonly field: string | undefined;
  public readonly details: unknown;

  constructor(opts: ApiErrorOptions) {
    super(opts.message);
    this.name = 'ApiError';
    this.code = opts.code;
    this.httpStatus = opts.httpStatus;
    this.requestId = opts.requestId;
    this.field = opts.field;
    this.details = opts.details;
  }

  isAuthFailure(): boolean {
    return (
      this.code === 'EXPIRED_TOKEN' ||
      this.code === 'INVALID_TOKEN' ||
      this.code === 'MISSING_TOKEN'
    );
  }

  isValidation(): boolean {
    return this.httpStatus === 422;
  }
}

/**
 * Convert an arbitrary AxiosError into a stable ApiError.
 *
 * The Backend's error envelope is `{ error: { code, message, request_id } }`.
 * Pydantic 422 responses come back with a `detail: [{ loc, msg, type }, ...]`
 * shape — we pick the first one and lift `loc[-1]` as `field`.
 */
export function fromAxiosError(err: AxiosError, fallbackRequestId: string): ApiError {
  // No response = network error / CORS / aborted.
  if (!err.response) {
    return new ApiError({
      code: err.code === 'ERR_CANCELED' ? 'UNKNOWN_ERROR' : 'NETWORK_ERROR',
      message:
        err.code === 'ERR_NETWORK'
          ? 'Cannot reach the server. Check your connection and try again.'
          : err.message || 'Network error.',
      httpStatus: 0,
      requestId: fallbackRequestId,
    });
  }

  const httpStatus = err.response.status;
  const headerRequestId =
    (err.response.headers?.[REQUEST_ID_HEADER.toLowerCase()] as string | undefined) ??
    fallbackRequestId;

  const data = err.response.data as unknown;

  // Standard Backend error envelope.
  if (isApiErrorEnvelope(data)) {
    return new ApiError({
      code: data.error.code,
      message: data.error.message,
      httpStatus,
      requestId: data.error.request_id || headerRequestId,
    });
  }

  // FastAPI / Pydantic raw validation envelope (defensive — Backend wraps it,
  // but middleware misfires happen).
  if (
    httpStatus === 422 &&
    typeof data === 'object' &&
    data !== null &&
    'detail' in data &&
    Array.isArray((data as { detail: unknown }).detail)
  ) {
    const detail = (data as { detail: Array<{ loc?: unknown[]; msg?: string }> }).detail;
    const first = detail[0];
    const loc = Array.isArray(first?.loc) ? first.loc : [];
    const field = loc.length > 0 ? String(loc[loc.length - 1]) : undefined;
    return new ApiError({
      code: 'VALIDATION_ERROR',
      message: first?.msg ?? 'Validation error.',
      httpStatus,
      requestId: headerRequestId,
      field,
      details: detail,
    });
  }

  return new ApiError({
    code: 'UNKNOWN_ERROR',
    message: err.message || `Request failed with status ${httpStatus}.`,
    httpStatus,
    requestId: headerRequestId,
    details: data,
  });
}

function isApiErrorEnvelope(data: unknown): data is ApiErrorEnvelope {
  if (typeof data !== 'object' || data === null) return false;
  const errObj = (data as { error?: unknown }).error;
  if (typeof errObj !== 'object' || errObj === null) return false;
  return (
    typeof (errObj as { code?: unknown }).code === 'string' &&
    typeof (errObj as { message?: unknown }).message === 'string'
  );
}
