import { describe, it, expect } from 'vitest';

import type {
  Customer,
  PurchaseOrder,
  SalesOrder,
  StockMovement,
  Vendor,
} from '@/types/api.types';

import {
  directionBadge,
  movementParty,
  movementReference,
  reasonLabel,
  toAdjustmentPayload,
  type PartyMaps,
} from './sm.transform';

function movement(overrides: Partial<StockMovement> = {}): StockMovement {
  return {
    id: 'm1',
    item_id: 'i1',
    direction: 'IN',
    reason: 'ADJUSTMENT',
    quantity: '10',
    signed_quantity: '10',
    stock_before: '0',
    stock_after: '10',
    reference_type: null,
    reference_id: null,
    remarks: 'Recount correction',
    created_by_user_id: 'u1',
    created_at: '2026-05-01T10:00:00Z',
    ...overrides,
  };
}

describe('directionBadge / reasonLabel', () => {
  it('maps direction with arrows', () => {
    expect(directionBadge('IN')).toEqual({ variant: 'success', label: 'IN ↑' });
    expect(directionBadge('OUT')).toEqual({ variant: 'danger', label: 'OUT ↓' });
  });

  it('humanises reason', () => {
    expect(reasonLabel('PURCHASE')).toBe('Purchase');
    expect(reasonLabel('SALE')).toBe('Sale');
    expect(reasonLabel('ADJUSTMENT')).toBe('Adjustment');
  });
});

describe('movementReference', () => {
  it('links a purchase-order reference', () => {
    expect(
      movementReference(movement({ reason: 'PURCHASE', reference_type: 'PURCHASE_ORDER', reference_id: 'po1' })),
    ).toEqual({ label: 'Purchase order', kind: 'purchase-order', id: 'po1' });
  });

  it('links a sales-order reference', () => {
    expect(
      movementReference(movement({ reason: 'SALE', reference_type: 'SALES_ORDER', reference_id: 'so1' })),
    ).toEqual({ label: 'Sales order', kind: 'sales-order', id: 'so1' });
  });

  it('falls back to remarks then an em dash for adjustments', () => {
    expect(movementReference(movement({ remarks: 'Recount line B' }))).toMatchObject({
      kind: null,
      label: 'Recount line B',
    });
    expect(movementReference(movement({ remarks: null })).label).toBe('—');
  });
});

describe('movementParty', () => {
  const maps: PartyMaps = {
    purchaseOrders: new Map([['po1', { id: 'po1', vendor_id: 'v1' } as PurchaseOrder]]),
    salesOrders: new Map([['so1', { id: 'so1', customer_id: 'c1' } as SalesOrder]]),
    vendors: new Map([['v1', { id: 'v1', vendor_name: 'Acme Steel Co' } as Vendor]]),
    customers: new Map([['c1', { id: 'c1', company_name: 'Bottlers Ltd' } as Customer]]),
  };

  it('resolves a purchase movement to its vendor', () => {
    const m = movement({ reason: 'PURCHASE', reference_type: 'PURCHASE_ORDER', reference_id: 'po1' });
    expect(movementParty(m, maps)).toBe('Acme Steel Co');
  });

  it('resolves a sale movement to its customer', () => {
    const m = movement({ reason: 'SALE', reference_type: 'SALES_ORDER', reference_id: 'so1' });
    expect(movementParty(m, maps)).toBe('Bottlers Ltd');
  });

  it('returns an em dash for adjustments (no reference)', () => {
    expect(movementParty(movement(), maps)).toBe('—');
  });

  it('returns an em dash when the reference is not yet loaded', () => {
    const m = movement({ reason: 'PURCHASE', reference_type: 'PURCHASE_ORDER', reference_id: 'po-unknown' });
    expect(movementParty(m, maps)).toBe('—');
  });
});

describe('toAdjustmentPayload', () => {
  it('maps the form values straight through', () => {
    expect(
      toAdjustmentPayload({ item_id: 'i1', direction: 'OUT', quantity: '5', remarks: 'Damaged units' }),
    ).toEqual({ item_id: 'i1', direction: 'OUT', quantity: '5', remarks: 'Damaged units' });
  });
});
