/**
 * Per-request correlation IDs.
 *
 * The Backend echoes its `X-Request-ID` on every response (and embeds it in
 * the error envelope). We attach a client-generated one on the request side
 * so a UUID exists even before the response lands — useful in error logs
 * fired from the request interceptor itself (e.g. network failure).
 */

export function newRequestId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // Fallback for older test environments.
  const rand = () => Math.random().toString(16).slice(2, 10);
  return `${rand()}-${rand()}-${rand()}-${rand()}`;
}

export const REQUEST_ID_HEADER = 'X-Request-ID';
