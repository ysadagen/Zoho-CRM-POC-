/**
 * Auth session storage: access token lives in-memory only; non-sensitive
 * session metadata (expiry, user) is kept in sessionStorage so the user
 * info survives a React re-render but not a tab close.
 *
 * XSS cannot reach an in-memory token, unlike localStorage. The trade-off
 * is that a hard page refresh logs the user out — acceptable for this app.
 */
import { logger } from '@/lib/logger';
import type { User } from '@/types/api.types';

const SESSION_META_KEY = 'adagen.session.meta';

export interface StoredSession {
  token: string;
  /** Epoch milliseconds — computed from the login response's `expires_in`. */
  expiresAt: number;
  user: User;
}

interface SessionMeta {
  expiresAt: number;
  user: User;
}

// Access token lives only in memory — never in DOM storage.
// XSS cannot read it; the trade-off is that a page refresh requires re-login.
let _token: string | null = null;

export function setSession(session: StoredSession): void {
  _token = session.token;
  const meta: SessionMeta = { expiresAt: session.expiresAt, user: session.user };
  sessionStorage.setItem(SESSION_META_KEY, JSON.stringify(meta));
}

export function clearSession(): void {
  _token = null;
  sessionStorage.removeItem(SESSION_META_KEY);
}

/** Returns the stored session, or null if absent, malformed, or expired. */
export function getSession(): StoredSession | null {
  if (!_token) return null;
  const raw = sessionStorage.getItem(SESSION_META_KEY);
  if (!raw) {
    _token = null;
    return null;
  }
  try {
    const meta = JSON.parse(raw) as SessionMeta;
    if (!meta?.user || typeof meta.expiresAt !== 'number') {
      clearSession();
      return null;
    }
    if (Date.now() >= meta.expiresAt) {
      clearSession();
      return null;
    }
    return { token: _token, expiresAt: meta.expiresAt, user: meta.user };
  } catch {
    logger.warn('auth.session.corrupt');
    clearSession();
    return null;
  }
}

export function getToken(): string | null {
  return _token;
}
