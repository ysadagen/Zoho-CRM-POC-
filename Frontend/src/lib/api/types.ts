/**
 * Re-exports of the API envelope types so feature `*.api.ts` files don't
 * reach into `types/`. Keeps the import graph tidy.
 */

export type { Paginated, ApiErrorEnvelope } from '@/types/api.types';
