import { describe, it, expect, afterEach } from 'vitest';

import type { User } from '@/types/api.types';

import { clearSession, getSession, getToken, setSession, type StoredSession } from './token-storage';

const USER: User = {
  id: 'u-1',
  email: 'a@b.com',
  full_name: 'A B',
  is_admin: false,
  is_active: true,
  created_at: '',
  updated_at: '',
};

function session(overrides: Partial<StoredSession> = {}): StoredSession {
  return { token: 'tok', expiresAt: Date.now() + 60_000, user: USER, ...overrides };
}

afterEach(() => clearSession());

describe('token-storage', () => {
  it('round-trips a valid session', () => {
    setSession(session());
    expect(getSession()?.token).toBe('tok');
    expect(getToken()).toBe('tok');
  });

  it('returns null when there is no session', () => {
    expect(getSession()).toBeNull();
    expect(getToken()).toBeNull();
  });

  it('treats an expired session as absent and clears it', () => {
    setSession(session({ expiresAt: Date.now() - 1 }));
    expect(getSession()).toBeNull();
    expect(localStorage.getItem('adagen.session')).toBeNull();
  });

  it('discards corrupt storage', () => {
    localStorage.setItem('adagen.session', 'not-json');
    expect(getSession()).toBeNull();
  });
});
