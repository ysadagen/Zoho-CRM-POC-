import { describe, it, expect } from 'vitest';

import type { Item, PurchaseOrder } from '@/types/api.types';

import { EMPTY_PO } from './po.schema';
import {
  estimatedTotal,
  lineTotal,
  poStatusBadge,
  receiveDeltas,
  toPoCreatePayload,
} from './po.transform';

function item(overrides: Partial<Item> = {}): Item {
  return {
    id: 'i1',
    sku: 'RAW-1',
    name: 'Raw Steel',
    description: null,
    type: 'RAW',
    category: null,
    unit_of_measure: 'kg',
    stock_quantity: '0',
    reorder_threshold: null,
    unit_price: '0',
    status: 'NO_STOCK',
    is_active: true,
    created_at: '',
    updated_at: '',
    ...overrides,
  };
}

describe('poStatusBadge', () => {
  it('maps status', () => {
    expect(poStatusBadge('DRAFT')).toEqual({ variant: 'ink', label: 'Draft' });
    expect(poStatusBadge('RECEIVED')).toEqual({ variant: 'success', label: 'Received' });
  });
});

describe('lineTotal / estimatedTotal', () => {
  it('computes a line total only when both qty + price exist', () => {
    expect(lineTotal('10', '5')).toBe(50);
    expect(lineTotal('10', '')).toBeNull();
  });

  it('sums only the priced lines', () => {
    expect(
      estimatedTotal([
        { quantity: '10', unit_price: '5' },
        { quantity: '3', unit_price: '' },
      ]),
    ).toBe(50);
  });
});

describe('toPoCreatePayload', () => {
  it('drops blank unit_price, eta and notes', () => {
    const payload = toPoCreatePayload({
      ...EMPTY_PO,
      vendor_id: 'v1',
      items: [{ item_id: 'i1', quantity: '100', unit_price: '' }],
    });
    expect(payload).toEqual({ vendor_id: 'v1', items: [{ item_id: 'i1', quantity: '100' }] });
  });

  it('keeps a provided unit_price, eta and notes', () => {
    const payload = toPoCreatePayload({
      vendor_id: 'v1',
      expected_delivery_date: '2026-07-15',
      notes: 'rush',
      items: [{ item_id: 'i1', quantity: '100', unit_price: '45' }],
    });
    expect(payload).toMatchObject({
      expected_delivery_date: '2026-07-15',
      notes: 'rush',
      items: [{ item_id: 'i1', quantity: '100', unit_price: '45' }],
    });
  });
});

describe('receiveDeltas', () => {
  it('builds +qty unit name lines, resolving item names', () => {
    const po = {
      items: [{ item_id: 'i1', quantity: '100' }],
    } as PurchaseOrder;
    const map = new Map<string, Item>([['i1', item({ name: 'Raw Steel', unit_of_measure: 'kg' })]]);
    expect(receiveDeltas(po, map)).toEqual([{ itemId: 'i1', label: '+100 kg Raw Steel' }]);
  });
});
