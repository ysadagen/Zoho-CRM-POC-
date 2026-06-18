/**
 * The only place auth tokens live (localStorage). The api client reads the
 * token through `getToken` (wired in AuthProvider) so `lib/api/` never imports
 * this module — avoiding a layering cycle.
 */
import { logger } from '@/lib/logger';
import type { User } from '@/types/api.types';

const STORAGE_KEY = 'adagen.session';

export interface StoredSession {
  token: string;
  /** Epoch milliseconds — computed from the login response's `expires_in`. */
  expiresAt: number;
  user: User;
}

export function setSession(session: StoredSession): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  localStorage.removeItem(STORAGE_KEY);
}

/** Returns the stored session, or null if absent, malformed, or expired. */
export function getSession(): StoredSession | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    // Cast is provisional: the field checks immediately below validate the
    // runtime shape before we ever return or trust `parsed`.
    const parsed = JSON.parse(raw) as StoredSession;
    if (!parsed?.token || typeof parsed.expiresAt !== 'number' || !parsed.user) {
      clearSession();
      return null;
    }
    if (Date.now() >= parsed.expiresAt) {
      clearSession();
      return null;
    }
    return parsed;
  } catch {
    logger.warn('auth.session.corrupt');
    clearSession();
    return null;
  }
}

export function getToken(): string | null {
  return getSession()?.token ?? null;
}
