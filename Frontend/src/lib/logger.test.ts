import { describe, it, expect, vi, beforeEach } from 'vitest';

import { logger } from './logger';

describe('logger', () => {
  // Re-created each test: `restoreMocks: true` detaches spies between tests,
  // so they must be installed in beforeEach to actually intercept console.
  let debugSpy: ReturnType<typeof vi.spyOn>;
  let infoSpy: ReturnType<typeof vi.spyOn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;
  let errorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {});
    infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('redacts secret fields before emit and keeps the scope', () => {
    logger.info('auth.login', { email: 'a@b.com', password: 'hunter2', access_token: 'tok' });
    expect(infoSpy).toHaveBeenCalledTimes(1);
    const payload = infoSpy.mock.calls[0]?.[1] as Record<string, unknown>;
    expect(payload.password).toBe('[redacted]');
    expect(payload.access_token).toBe('[redacted]');
    expect(payload.email).toBe('a@b.com');
    expect(payload.scope).toBe('auth.login');
  });

  it('redacts case-insensitively', () => {
    logger.error('x', { Authorization: 'Bearer z' });
    const payload = errorSpy.mock.calls[0]?.[1] as Record<string, unknown>;
    expect(payload.Authorization).toBe('[redacted]');
  });

  it('suppresses debug below the info threshold (non-dev test mode)', () => {
    logger.debug('noisy', { a: 1 });
    expect(debugSpy).not.toHaveBeenCalled();
  });

  it('emits warn and error', () => {
    logger.warn('w');
    logger.error('e');
    expect(warnSpy).toHaveBeenCalledOnce();
    expect(errorSpy).toHaveBeenCalledOnce();
  });
});
