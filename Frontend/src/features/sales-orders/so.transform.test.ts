import { describe, it, expect } from 'vitest';

import type { Batch, Item, SalesOrder } from '@/types/api.types';

import { EMPTY_SO } from './so.schema';
import {
  hasShortLine,
  shipDeltas,
  shippableLotsByItem,
  soLineStock,
  soStatusBadge,
  toSoCreatePayload,
} from './so.transform';

function batch(overrides: Partial<Batch> = {}): Batch {
  return {
    id: 'b1',
    item_id: 'i1',
    batch_number: 'LOT-1',
    batch_status: 'RELEASED',
    batch_received_date: null,
    manufacturing_date: null,
    expiry_date: '2035-01-01',
    quantity: '50',
    initial_quantity: '50',
    unit_cost: null,
    storage_location: null,
    vendor_id: null,
    received_via_po_id: null,
    is_expired: false,
    created_by_user_id: 'u1',
    updated_by_user_id: 'u1',
    created_at: '',
    updated_at: '',
    ...overrides,
  };
}

function item(overrides: Partial<Item> = {}): Item {
  return {
    id: 'i1',
    sku: 'FIN-1',
    name: 'Bottle 1L',
    description: null,
    type: 'FINISHED',
    category: null,
    unit_of_measure: 'pcs',
    stock_quantity: '100',
    reorder_threshold: '20',
    unit_price: '45',
    standard_cost: null,
    storage_condition: null,
    shelf_life_days: null,
    raw_detail: null,
    finished_detail: null,
    status: 'IN_STOCK',
    is_active: true,
    created_at: '',
    updated_at: '',
    ...overrides,
  };
}

describe('soStatusBadge', () => {
  it('maps status', () => {
    expect(soStatusBadge('DRAFT')).toEqual({ variant: 'ink', label: 'Draft' });
    expect(soStatusBadge('SHIPPED')).toEqual({ variant: 'success', label: 'Shipped' });
  });
});

describe('soLineStock', () => {
  it('returns null when no item is picked', () => {
    expect(soLineStock('5', undefined)).toBeNull();
  });

  it('flags short when qty exceeds stock', () => {
    const state = soLineStock('120', item({ stock_quantity: '100' }));
    expect(state?.variant).toBe('short');
    expect(state?.label).toContain('short by 20');
  });

  it('warns when fulfilling drops below the reorder threshold', () => {
    const state = soLineStock('90', item({ stock_quantity: '100', reorder_threshold: '20' }));
    expect(state?.variant).toBe('warn'); // 100 - 90 = 10 < 20
  });

  it('is ok when stock comfortably covers the line', () => {
    const state = soLineStock('10', item({ stock_quantity: '100', reorder_threshold: '20' }));
    expect(state?.variant).toBe('ok');
    expect(state?.label).toContain('100 pcs in stock');
  });
});

describe('hasShortLine', () => {
  it('detects any line ordering more than current stock', () => {
    const items = new Map<string, Item>([['i1', item({ stock_quantity: '5' })]]);
    expect(hasShortLine([{ item_id: 'i1', quantity: '10', unit_price: '', batch_id: '' }], items)).toBe(true);
    expect(hasShortLine([{ item_id: 'i1', quantity: '3', unit_price: '', batch_id: '' }], items)).toBe(false);
    // Unknown / unpicked item is not "short".
    expect(hasShortLine([{ item_id: '', quantity: '99', unit_price: '', batch_id: '' }], items)).toBe(false);
  });
});

describe('toSoCreatePayload', () => {
  it('drops blank optionals', () => {
    const payload = toSoCreatePayload({
      ...EMPTY_SO,
      customer_id: 'c1',
      items: [{ item_id: 'i1', quantity: '5', unit_price: '', batch_id: '' }],
    });
    expect(payload).toEqual({ customer_id: 'c1', items: [{ item_id: 'i1', quantity: '5' }] });
  });

  it('carries a chosen lot through as batch_id (#9)', () => {
    const payload = toSoCreatePayload({
      ...EMPTY_SO,
      customer_id: 'c1',
      items: [{ item_id: 'i1', quantity: '5', unit_price: '', batch_id: 'b9' }],
    });
    expect(payload.items[0]).toEqual({ item_id: 'i1', quantity: '5', batch_id: 'b9' });
  });
});

describe('shippableLotsByItem', () => {
  it('keeps in-stock, non-expired lots and groups them earliest-expiry first', () => {
    const map = shippableLotsByItem(
      [
        batch({ id: 'late', expiry_date: '2035-01-01' }),
        batch({ id: 'early', expiry_date: '2030-01-01' }),
        batch({ id: 'empty', expiry_date: '2035-01-01', quantity: '0' }),
        batch({ id: 'expired', expiry_date: '2020-01-01' }),
        batch({ id: 'other', item_id: 'i2', expiry_date: '2031-01-01' }),
      ],
      '2026-06-15',
    );
    expect(map.get('i1')?.map((l) => l.id)).toEqual(['early', 'late']); // sorted, no empty/expired
    expect(map.get('i2')?.map((l) => l.id)).toEqual(['other']);
  });
});

describe('shipDeltas', () => {
  it('builds -qty unit name lines', () => {
    const so = { items: [{ item_id: 'i1', quantity: '120' }] } as SalesOrder;
    const map = new Map<string, Item>([['i1', item({ name: 'Bottle 1L', unit_of_measure: 'pcs' })]]);
    expect(shipDeltas(so, map)).toEqual([{ itemId: 'i1', label: '-120 pcs Bottle 1L' }]);
  });
});
