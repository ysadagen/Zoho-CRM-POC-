import { describe, it, expect } from 'vitest';
import type { AxiosError } from 'axios';

import { ApiError, fromAxiosError } from './errors';

// Minimal AxiosError factories — we only set the fields `fromAxiosError` reads.
// Cast through `unknown` because we intentionally build partial shapes.
function networkError(code: string): AxiosError {
  return { code, message: 'net', config: { url: '/x' } } as unknown as AxiosError;
}
function withResponse(
  status: number,
  data: unknown,
  headers: Record<string, string> = {},
): AxiosError {
  return {
    message: 'err',
    config: { url: '/x' },
    response: { status, data, headers },
  } as unknown as AxiosError;
}

describe('fromAxiosError', () => {
  it('maps a missing response to NETWORK_ERROR with the fallback request id', () => {
    const e = fromAxiosError(networkError('ERR_NETWORK'), 'fallback-1');
    expect(e).toBeInstanceOf(ApiError);
    expect(e.code).toBe('NETWORK_ERROR');
    expect(e.httpStatus).toBe(0);
    expect(e.requestId).toBe('fallback-1');
    expect(e.message).toMatch(/reach the server/i);
  });

  it('maps a canceled request to UNKNOWN_ERROR', () => {
    expect(fromAxiosError(networkError('ERR_CANCELED'), 'fb').code).toBe('UNKNOWN_ERROR');
  });

  it('reads the Backend error envelope (code, message, request_id)', () => {
    const e = fromAxiosError(
      withResponse(409, {
        error: { code: 'DUPLICATE_SKU', message: 'dup', request_id: 'srv-9' },
      }),
      'fb',
    );
    expect(e.code).toBe('DUPLICATE_SKU');
    expect(e.message).toBe('dup');
    expect(e.httpStatus).toBe(409);
    expect(e.requestId).toBe('srv-9');
  });

  it('falls back to the X-Request-ID header when the envelope omits request_id', () => {
    const e = fromAxiosError(
      withResponse(
        409,
        { error: { code: 'DUPLICATE_SKU', message: 'dup', request_id: '' } },
        { 'x-request-id': 'hdr-7' },
      ),
      'fb',
    );
    expect(e.requestId).toBe('hdr-7');
  });

  it('extracts the field from a Pydantic 422 detail array', () => {
    const e = fromAxiosError(
      withResponse(
        422,
        { detail: [{ loc: ['body', 'email'], msg: 'invalid email' }] },
        { 'x-request-id': 'h' },
      ),
      'fb',
    );
    expect(e.code).toBe('VALIDATION_ERROR');
    expect(e.field).toBe('email');
    expect(e.message).toBe('invalid email');
    expect(e.isValidation()).toBe(true);
  });

  it('falls back to UNKNOWN_ERROR for an unrecognised body shape', () => {
    const e = fromAxiosError(withResponse(500, 'oops'), 'fb');
    expect(e.code).toBe('UNKNOWN_ERROR');
    expect(e.httpStatus).toBe(500);
  });
});

describe('ApiError', () => {
  it('flags auth-failure codes', () => {
    for (const code of ['EXPIRED_TOKEN', 'INVALID_TOKEN', 'MISSING_TOKEN'] as const) {
      const e = new ApiError({ code, message: 'x', httpStatus: 401, requestId: 'r' });
      expect(e.isAuthFailure()).toBe(true);
    }
    const dup = new ApiError({ code: 'DUPLICATE_SKU', message: 'x', httpStatus: 409, requestId: 'r' });
    expect(dup.isAuthFailure()).toBe(false);
  });

  it('isValidation is true only for HTTP 422', () => {
    const v = new ApiError({ code: 'VALIDATION_ERROR', message: 'x', httpStatus: 422, requestId: 'r' });
    const b = new ApiError({ code: 'X', message: 'x', httpStatus: 400, requestId: 'r' });
    expect(v.isValidation()).toBe(true);
    expect(b.isValidation()).toBe(false);
  });
});
