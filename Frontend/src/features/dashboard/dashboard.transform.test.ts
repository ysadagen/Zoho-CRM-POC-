import { describe, it, expect } from 'vitest';

import type { Item, StockMovement } from '@/types/api.types';

import {
  buildKpis,
  firstName,
  greeting,
  isLowStock,
  lowStockItems,
  movementBadge,
  movementReference,
  toLowStockVM,
  toMovementVM,
  totalStockValue,
} from './dashboard.transform';

function item(overrides: Partial<Item> = {}): Item {
  return {
    id: 'i1',
    sku: 'SKU-1',
    name: 'Item 1',
    description: null,
    type: 'RAW',
    category: null,
    unit_of_measure: 'kg',
    stock_quantity: '100',
    reorder_threshold: '50',
    unit_price: '10',
    standard_cost: null,
    storage_condition: null,
    shelf_life_days: null,
    raw_detail: null,
    finished_detail: null,
    status: 'IN_STOCK',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function movement(overrides: Partial<StockMovement> = {}): StockMovement {
  return {
    id: 'm1',
    item_id: 'i1',
    direction: 'OUT',
    reason: 'SALE',
    quantity: '120',
    signed_quantity: '-120',
    stock_before: '200',
    stock_after: '80',
    reference_type: 'SALES_ORDER',
    reference_id: 'so1',
    batch_id: null,
    remarks: null,
    created_by_user_id: 'u1',
    created_at: '2026-05-28T14:32:00Z',
    ...overrides,
  };
}

describe('totalStockValue', () => {
  it('sums stock_quantity × unit_price across items', () => {
    const value = totalStockValue([
      item({ stock_quantity: '100', unit_price: '10' }),
      item({ stock_quantity: '5', unit_price: '2.5' }),
    ]);
    expect(value).toBe(1012.5);
  });

  it('is zero for an empty catalog', () => {
    expect(totalStockValue([])).toBe(0);
  });
});

describe('isLowStock / lowStockItems', () => {
  it('treats LOW_STOCK and NO_STOCK as low, IN_STOCK as fine', () => {
    expect(isLowStock(item({ status: 'LOW_STOCK' }))).toBe(true);
    expect(isLowStock(item({ status: 'NO_STOCK' }))).toBe(true);
    expect(isLowStock(item({ status: 'IN_STOCK' }))).toBe(false);
  });

  it('filters a catalog down to the low ones', () => {
    const low = lowStockItems([
      item({ id: 'a', status: 'IN_STOCK' }),
      item({ id: 'b', status: 'LOW_STOCK' }),
      item({ id: 'c', status: 'NO_STOCK' }),
    ]);
    expect(low.map((i) => i.id)).toEqual(['b', 'c']);
  });
});

describe('toLowStockVM', () => {
  it('builds a view-model with ratio, meta and critical flag', () => {
    const vm = toLowStockVM(
      item({
        id: 'x',
        sku: 'ITM-2',
        name: 'Raw Steel',
        type: 'RAW',
        status: 'LOW_STOCK',
        stock_quantity: '40',
        reorder_threshold: '100',
        unit_of_measure: 'kg',
      }),
    );
    expect(vm).toMatchObject({
      id: 'x',
      name: 'Raw Steel',
      meta: 'ITM-2 · Raw Material',
      value: '40 / 100 kg',
      pct: 40,
      critical: true,
    });
  });

  it('labels finished products and flags above-half as non-critical', () => {
    const vm = toLowStockVM(
      item({ type: 'FINISHED', status: 'LOW_STOCK', stock_quantity: '85', reorder_threshold: '100' }),
    );
    expect(vm.meta).toContain('Finished Product');
    expect(vm.pct).toBe(85);
    expect(vm.critical).toBe(false);
  });

  it('handles a missing threshold (no-stock item) without dividing by zero', () => {
    const vm = toLowStockVM(
      item({ status: 'NO_STOCK', stock_quantity: '0', reorder_threshold: null, unit_of_measure: 'pcs' }),
    );
    expect(vm.pct).toBe(0);
    expect(vm.value).toBe('0 pcs');
    expect(vm.critical).toBe(true);
  });
});

describe('movementBadge / movementReference', () => {
  it('maps reason to the canonical badge', () => {
    expect(movementBadge(movement({ reason: 'PURCHASE', direction: 'IN' }))).toEqual({
      variant: 'success',
      label: 'Purchase In',
    });
    expect(movementBadge(movement({ reason: 'SALE', direction: 'OUT' }))).toEqual({
      variant: 'danger',
      label: 'Sale Out',
    });
    expect(movementBadge(movement({ reason: 'ADJUSTMENT' }))).toEqual({
      variant: 'warn',
      label: 'Adjustment',
    });
  });

  it('humanises the reference, falling back to remarks then a default', () => {
    expect(movementReference(movement({ reference_type: 'PURCHASE_ORDER' }))).toBe('Purchase order');
    expect(movementReference(movement({ reference_type: 'SALES_ORDER' }))).toBe('Sales order');
    expect(
      movementReference(movement({ reference_type: null, reference_id: null, remarks: 'Recount line B' })),
    ).toBe('Recount line B');
    expect(
      movementReference(movement({ reference_type: null, reference_id: null, remarks: null })),
    ).toBe('Manual adjustment');
  });
});

describe('toMovementVM', () => {
  it('resolves the item name + unit and signs the quantity', () => {
    const items = new Map<string, Item>([['i1', item({ name: 'Bottle 1L', unit_of_measure: 'pcs' })]]);
    const vm = toMovementVM(movement({ signed_quantity: '-120', reason: 'SALE' }), items);
    expect(vm).toMatchObject({
      id: 'm1',
      item: 'Bottle 1L',
      movement: 'Sale Out',
      badgeVariant: 'danger',
      qty: '−120 pcs',
      reference: 'Sales order',
    });
  });

  it('falls back to a placeholder name when the item is not in the map', () => {
    const vm = toMovementVM(movement({ item_id: 'gone' }), new Map());
    expect(vm.item).toBe('Unknown item');
  });
});

describe('buildKpis', () => {
  it('produces the five tiles with live counts and an honest CRM placeholder', () => {
    const kpis = buildKpis({
      items: [
        item({ status: 'IN_STOCK', stock_quantity: '10', unit_price: '5' }),
        item({ status: 'LOW_STOCK' }),
      ],
      draftPoCount: 3,
      draftSoCount: 2,
    });
    expect(kpis).toHaveLength(5);
    expect(kpis[1]).toMatchObject({ label: 'Low Stock Items', value: '1' });
    expect(kpis[2]).toMatchObject({ label: 'Open Purchase Orders', value: '3' });
    expect(kpis[3]).toMatchObject({ label: 'Open Sales Orders', value: '2' });
    expect(kpis[4]).toMatchObject({ label: 'CRM Sync Health', value: '—' });
    expect(kpis[0]?.label).toBe('Total Stock Value');
  });
});

describe('greeting / firstName', () => {
  it('picks the part of day', () => {
    expect(greeting(9)).toBe('Good morning');
    expect(greeting(14)).toBe('Good afternoon');
    expect(greeting(20)).toBe('Good evening');
    expect(greeting(2)).toBe('Good evening');
  });

  it('takes the first whitespace-delimited token', () => {
    expect(firstName('Ravi Menon')).toBe('Ravi');
    expect(firstName('  Ann  Marie ')).toBe('Ann');
    expect(firstName('')).toBe('');
  });
});
