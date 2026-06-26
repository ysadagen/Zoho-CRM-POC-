import { describe, it, expect } from 'vitest';

import type { Vendor, VendorItemTerm } from '@/types/api.types';

import {
  termToFormValues,
  toTermCreatePayload,
  toTermUpdatePayload,
  toVendorPayload,
  vendorToFormValues,
} from './vendor.transform';
import { EMPTY_TERM, EMPTY_VENDOR } from './vendor.schema';

function vendor(overrides: Partial<Vendor> = {}): Vendor {
  return {
    id: 'v1',
    vendor_name: 'Steelco',
    contact_person: 'Ravi',
    email: 'sales@steelco.test',
    phone: '123',
    vendor_code: 'STL-1',
    gstin: 'GST9',
    is_active: true,
    address: null,
    notes: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function term(overrides: Partial<VendorItemTerm> = {}): VendorItemTerm {
  return {
    id: 't1',
    vendor_id: 'v1',
    item_id: 'i1',
    rate: '150.00',
    discount_percent: '5.00',
    effective_from: '2026-01-01',
    effective_to: '2026-12-31',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

describe('vendor payload', () => {
  it('keeps the name and drops empty optionals', () => {
    expect(toVendorPayload({ ...EMPTY_VENDOR, vendor_name: 'Steelco' })).toEqual({ vendor_name: 'Steelco' });
  });

  it('seeds the edit form from a vendor', () => {
    expect(vendorToFormValues(vendor({ contact_person: null, gstin: null }))).toMatchObject({
      vendor_name: 'Steelco',
      contact_person: '',
      gstin: '',
    });
  });
});

describe('term payloads', () => {
  it('create drops empty discount + effective_to', () => {
    expect(
      toTermCreatePayload({ ...EMPTY_TERM, item_id: 'i1', rate: '150', effective_from: '2026-01-01' }),
    ).toEqual({ item_id: 'i1', rate: '150', effective_from: '2026-01-01' });
  });

  it('create carries discount + effective_to when present', () => {
    expect(
      toTermCreatePayload({
        item_id: 'i1',
        rate: '150',
        discount_percent: '5',
        effective_from: '2026-01-01',
        effective_to: '2026-12-31',
      }),
    ).toMatchObject({ discount_percent: '5', effective_to: '2026-12-31' });
  });

  it('update never sends item_id and nulls a blank effective_to', () => {
    const payload = toTermUpdatePayload({
      item_id: 'i1',
      rate: '160',
      discount_percent: '',
      effective_from: '2026-02-01',
      effective_to: '',
    });
    expect(payload).toEqual({
      rate: '160',
      discount_percent: '0',
      effective_from: '2026-02-01',
      effective_to: null,
    });
    expect(payload).not.toHaveProperty('item_id');
  });

  it('seeds the term edit form, coercing a null effective_to', () => {
    expect(termToFormValues(term({ effective_to: null })).effective_to).toBe('');
  });
});
