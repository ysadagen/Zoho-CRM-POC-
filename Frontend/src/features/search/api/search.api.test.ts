import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/features/customers/api/customers.api', () => ({ listCustomers: vi.fn() }));
vi.mock('@/features/items/api/items.api', () => ({ listItems: vi.fn() }));
vi.mock('@/features/leads/api/leads.api', () => ({ listLeads: vi.fn() }));
vi.mock('@/features/vendors/api/vendors.api', () => ({ listVendors: vi.fn() }));

import { listCustomers } from '@/features/customers/api/customers.api';
import { listItems } from '@/features/items/api/items.api';
import { listLeads } from '@/features/leads/api/leads.api';
import { listVendors } from '@/features/vendors/api/vendors.api';
import { ApiError } from '@/lib/api/errors';

import { runSearch } from './search.api';

const page = <T,>(items: T[]) => ({ items, total: items.length, limit: 5, offset: 0 });

describe('runSearch', () => {
  beforeEach(() => vi.clearAllMocks());

  it('maps each source into a navigable group and forwards the trimmed query', async () => {
    vi.mocked(listCustomers).mockResolvedValue(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      page([{ id: 'c1', company_name: 'Acme', customer_code: null, city: null, email: 'a@b.c' }]) as any,
    );
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    vi.mocked(listItems).mockResolvedValue(page([{ id: 'i1', name: 'Bottle', sku: 'S1' }]) as any);
    vi.mocked(listVendors).mockResolvedValue(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      page([{ id: 'v1', vendor_name: 'Sup', vendor_code: null, email: null }]) as any,
    );
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    vi.mocked(listLeads).mockResolvedValue(page([{ id: 'l1', contact_name: 'Rep', email: 'r@b.c', phone: null }]) as any);

    const groups = await runSearch('  acme ');
    const [customers, items, vendors, leads] = groups;

    expect(customers).toMatchObject({ entity: 'customer', failed: false });
    // sublabel falls back customer_code → city → email.
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect(customers!.results[0]).toMatchObject({ label: 'Acme', sublabel: 'a@b.c', route: '/customers/c1' });
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect(items!.results[0]).toMatchObject({ label: 'Bottle', sublabel: 'S1', route: '/items/i1' });
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect(vendors!.results[0]).toMatchObject({ label: 'Sup', sublabel: null, route: '/vendors/v1' });
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect(leads!.results[0]).toMatchObject({ label: 'Rep', sublabel: 'r@b.c', route: '/leads/l1' });
    expect(vi.mocked(listCustomers)).toHaveBeenCalledWith({ search: 'acme', limit: 5, offset: 0 });
    expect(vi.mocked(listLeads)).toHaveBeenCalledWith({ search: 'acme', limit: 5, offset: 0 });
  });

  it('isolates failures per source — both ApiError and a generic Error mark only that group failed', async () => {
    vi.mocked(listCustomers).mockRejectedValue(
      new ApiError({ code: 'UNKNOWN_ERROR', message: 'x', httpStatus: 500, requestId: 'r1' }),
    );
    vi.mocked(listItems).mockRejectedValue(new Error('boom')); // non-ApiError log branch
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    vi.mocked(listVendors).mockResolvedValue(page([{ id: 'v1', vendor_name: 'Sup', vendor_code: 'V1', email: null }]) as any);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    vi.mocked(listLeads).mockResolvedValue(page([]) as any);

    const groups = await runSearch('acme');
    const [customers, items, vendors] = groups;

    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect(customers!.failed).toBe(true);
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect(customers!.results).toEqual([]);
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect(items!.failed).toBe(true);
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect(vendors!.failed).toBe(false);
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect(vendors!.results[0]?.sublabel).toBe('V1');
  });
});
