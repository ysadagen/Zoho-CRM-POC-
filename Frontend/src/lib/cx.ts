/**
 * Tiny class-name joiner (clsx-lite). Falsy parts are dropped so callers can
 * write `cx('btn', isActive && 'active')` without ternaries.
 */
export type ClassValue = string | false | null | undefined;

export function cx(...parts: ClassValue[]): string {
  return parts.filter(Boolean).join(' ');
}
