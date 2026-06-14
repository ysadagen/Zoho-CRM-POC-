import { describe, it, expect } from 'vitest';

import type { Item, SalesOrder } from '@/types/api.types';

import { EMPTY_SO } from './so.schema';
import {
  hasShortLine,
  shipDeltas,
  soLineStock,
  soStatusBadge,
  toSoCreatePayload,
} from './so.transform';

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
    expect(hasShortLine([{ item_id: 'i1', quantity: '10', unit_price: '' }], items)).toBe(true);
    expect(hasShortLine([{ item_id: 'i1', quantity: '3', unit_price: '' }], items)).toBe(false);
    // Unknown / unpicked item is not "short".
    expect(hasShortLine([{ item_id: '', quantity: '99', unit_price: '' }], items)).toBe(false);
  });
});

describe('toSoCreatePayload', () => {
  it('drops blank optionals', () => {
    const payload = toSoCreatePayload({
      ...EMPTY_SO,
      customer_id: 'c1',
      items: [{ item_id: 'i1', quantity: '5', unit_price: '' }],
    });
    expect(payload).toEqual({ customer_id: 'c1', items: [{ item_id: 'i1', quantity: '5' }] });
  });
});

describe('shipDeltas', () => {
  it('builds -qty unit name lines', () => {
    const so = { items: [{ item_id: 'i1', quantity: '120' }] } as SalesOrder;
    const map = new Map<string, Item>([['i1', item({ name: 'Bottle 1L', unit_of_measure: 'pcs' })]]);
    expect(shipDeltas(so, map)).toEqual([{ itemId: 'i1', label: '-120 pcs Bottle 1L' }]);
  });
});
