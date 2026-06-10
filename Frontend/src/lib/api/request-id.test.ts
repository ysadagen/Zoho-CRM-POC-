import { describe, it, expect, afterEach, vi } from 'vitest';

import { newRequestId, REQUEST_ID_HEADER } from './request-id';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('newRequestId', () => {
  it('uses crypto.randomUUID when available', () => {
    const id = newRequestId();
    expect(typeof id).toBe('string');
    expect(id.length).toBeGreaterThan(0);
  });

  it('falls back to a composed id when randomUUID is unavailable', () => {
    vi.stubGlobal('crypto', {});
    expect(newRequestId()).toMatch(/^[0-9a-f]*-[0-9a-f]*-[0-9a-f]*-[0-9a-f]*$/);
  });

  it('exposes the header name', () => {
    expect(REQUEST_ID_HEADER).toBe('X-Request-ID');
  });
});
