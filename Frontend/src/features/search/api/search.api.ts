/**
 * Global-search service layer.
 *
 * Search is inherently cross-feature, so it reuses the existing typed list
 * functions of each domain (`?search=` is supported by the Backend on all
 * three) rather than re-declaring endpoints. Each source is fetched
 * independently and failure-isolated: one source erroring marks only its own
 * group `failed` and never rejects the whole search.
 */

import { routes } from '@/app/routes';
import { listCustomers } from '@/features/customers/api/customers.api';
import { listItems } from '@/features/items/api/items.api';
import { listVendors } from '@/features/vendors/api/vendors.api';
import { ApiError } from '@/lib/api/errors';
import { logger } from '@/lib/logger';

import type { SearchEntity, SearchGroup, SearchResult } from '../search.types';

/** Hits to request (and show) per source. */
export const PER_SOURCE_LIMIT = 5;

function logSourceError(entity: SearchEntity, err: unknown): void {
  // Never log the raw query — it can contain customer names (PII). Log the
  // failing source plus the correlatable request id only.
  if (err instanceof ApiError) {
    logger.error('search.source_failed', {
      entity,
      code: err.code,
      httpStatus: err.httpStatus,
      requestId: err.requestId,
    });
  } else {
    logger.error('search.source_failed', { entity });
  }
}

async function customerGroup(query: string): Promise<SearchGroup> {
  const base = { entity: 'customer' as const, title: 'Customers', icon: 'user' as const };
  try {
    const page = await listCustomers({ search: query, limit: PER_SOURCE_LIMIT, offset: 0 });
    const results: SearchResult[] = page.items.map((c) => ({
      entity: 'customer',
      id: c.id,
      label: c.company_name,
      sublabel: c.customer_code ?? c.city ?? c.email,
      route: `${routes.customers}/${c.id}`,
    }));
    return { ...base, results, failed: false };
  } catch (err) {
    logSourceError('customer', err);
    return { ...base, results: [], failed: true };
  }
}

async function itemGroup(query: string): Promise<SearchGroup> {
  const base = { entity: 'item' as const, title: 'Items', icon: 'box' as const };
  try {
    const page = await listItems({ search: query, limit: PER_SOURCE_LIMIT, offset: 0 });
    const results: SearchResult[] = page.items.map((i) => ({
      entity: 'item',
      id: i.id,
      label: i.name,
      sublabel: i.sku,
      route: `${routes.items}/${i.id}`,
    }));
    return { ...base, results, failed: false };
  } catch (err) {
    logSourceError('item', err);
    return { ...base, results: [], failed: true };
  }
}

async function vendorGroup(query: string): Promise<SearchGroup> {
  const base = { entity: 'vendor' as const, title: 'Vendors', icon: 'truck' as const };
  try {
    const page = await listVendors({ search: query, limit: PER_SOURCE_LIMIT, offset: 0 });
    const results: SearchResult[] = page.items.map((v) => ({
      entity: 'vendor',
      id: v.id,
      label: v.vendor_name,
      sublabel: v.vendor_code ?? v.email,
      route: `${routes.vendors}/${v.id}`,
    }));
    return { ...base, results, failed: false };
  } catch (err) {
    logSourceError('vendor', err);
    return { ...base, results: [], failed: true };
  }
}

/** Fan out to every source in parallel. Groups come back in a stable order
 *  (Customers, Items, Vendors); each is independently failure-isolated. */
export async function runSearch(query: string): Promise<SearchGroup[]> {
  const trimmed = query.trim();
  return Promise.all([customerGroup(trimmed), itemGroup(trimmed), vendorGroup(trimmed)]);
}
