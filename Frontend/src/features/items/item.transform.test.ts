import { describe, it, expect } from 'vitest';

import type { Item, StockMovement } from '@/types/api.types';

import {
  itemStatusBadge,
  itemToEditValues,
  itemTypeBadge,
  summariseMovements,
  toCreatePayload,
  toUpdatePayload,
} from './item.transform';
import type { ItemCreateValues } from './item.schema';

function item(overrides: Partial<Item> = {}): Item {
  return {
    id: 'i1',
    sku: 'SKU-1',
    name: 'Item 1',
    description: 'desc',
    type: 'RAW',
    category: 'Bottles',
    unit_of_measure: 'kg',
    stock_quantity: '100',
    reorder_threshold: '50',
    unit_price: '10',
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
    direction: 'IN',
    reason: 'PURCHASE',
    quantity: '100',
    signed_quantity: '100',
    stock_before: '0',
    stock_after: '100',
    reference_type: 'PURCHASE_ORDER',
    reference_id: 'po1',
    remarks: null,
    created_by_user_id: 'u1',
    created_at: '2026-05-01T10:00:00Z',
    ...overrides,
  };
}

describe('badges', () => {
  it('maps item type', () => {
    expect(itemTypeBadge('RAW')).toEqual({ variant: 'info', label: 'RAW' });
    expect(itemTypeBadge('FINISHED')).toEqual({ variant: 'purple', label: 'FINISHED' });
  });

  it('maps item status', () => {
    expect(itemStatusBadge('IN_STOCK').variant).toBe('success');
    expect(itemStatusBadge('LOW_STOCK').variant).toBe('warn');
    expect(itemStatusBadge('NO_STOCK').variant).toBe('danger');
  });
});

describe('summariseMovements', () => {
  it('totals inbound/outbound and finds the latest timestamp', () => {
    const summary = summariseMovements([
      movement({ direction: 'IN', quantity: '100', created_at: '2026-05-01T10:00:00Z' }),
      movement({ direction: 'OUT', quantity: '30', created_at: '2026-05-03T09:00:00Z' }),
      movement({ direction: 'IN', quantity: '5', created_at: '2026-05-02T08:00:00Z' }),
    ]);
    expect(summary.totalInbound).toBe(105);
    expect(summary.totalOutbound).toBe(30);
    expect(summary.lastMovementAt).toBe('2026-05-03T09:00:00Z');
  });

  it('is zeroed with no movements', () => {
    expect(summariseMovements([])).toEqual({
      lastMovementAt: null,
      totalInbound: 0,
      totalOutbound: 0,
    });
  });
});

describe('toCreatePayload', () => {
  const base: ItemCreateValues = {
    sku: 'BOT-1L',
    name: '1L Bottle',
    type: 'FINISHED',
    category: 'Bottles',
    stock_quantity: '0',
    unit_of_measure: 'pcs',
    reorder_threshold: '',
    unit_price: '45',
    description: '',
  };

  it('includes only the filled optionals', () => {
    const payload = toCreatePayload({ ...base, stock_quantity: '', reorder_threshold: '', description: '' });
    expect(payload).toEqual({
      sku: 'BOT-1L',
      name: '1L Bottle',
      type: 'FINISHED',
      category: 'Bottles',
      unit_of_measure: 'pcs',
      unit_price: '45',
    });
  });

  it('carries optionals through when present', () => {
    const payload = toCreatePayload({
      ...base,
      description: 'Round bottle',
      stock_quantity: '500',
      reorder_threshold: '100',
    });
    expect(payload).toMatchObject({
      description: 'Round bottle',
      stock_quantity: '500',
      reorder_threshold: '100',
    });
  });
});

describe('toUpdatePayload', () => {
  it('only sends PATCH-safe fields', () => {
    const payload = toUpdatePayload({
      name: 'New name',
      category: 'Bottles',
      description: '',
      unit_of_measure: 'kg',
      reorder_threshold: '',
      unit_price: '12.50',
    });
    expect(payload).toEqual({
      name: 'New name',
      category: 'Bottles',
      unit_of_measure: 'kg',
      unit_price: '12.50',
    });
    expect(payload).not.toHaveProperty('sku');
    expect(payload).not.toHaveProperty('stock_quantity');
  });
});

describe('itemToEditValues', () => {
  it('seeds the form, coercing nulls to empty strings', () => {
    expect(
      itemToEditValues(item({ description: null, reorder_threshold: null, category: null })),
    ).toEqual({
      name: 'Item 1',
      category: '',
      description: '',
      unit_of_measure: 'kg',
      reorder_threshold: '',
      unit_price: '10',
    });
  });

  it('falls back to a known unit when the Backend unit is unfamiliar', () => {
    expect(itemToEditValues(item({ unit_of_measure: 'dozen' })).unit_of_measure).toBe('kg');
  });
});
