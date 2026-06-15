import { describe, it, expect } from 'vitest';

import type { PurchaseOrder } from '@/types/api.types';

import { EMPTY_PO } from './po.schema';
import {
  estimatedTotal,
  lineTotal,
  poStatusBadge,
  receiveDefaults,
  toPoCreatePayload,
  toReceivePayload,
} from './po.transform';

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

describe('receiveDefaults / toReceivePayload', () => {
  const po = {
    items: [
      { id: 'l1', item_id: 'i1', quantity: '100' },
      { id: 'l2', item_id: 'i2', quantity: '50' },
    ],
  } as PurchaseOrder;

  it('seeds one blank lot row per PO line with item_id prefilled', () => {
    expect(receiveDefaults(po)).toEqual({
      lines: [
        { item_id: 'i1', batch_number: '', expiry_date: '', manufacturing_date: '', storage_location: '' },
        { item_id: 'i2', batch_number: '', expiry_date: '', manufacturing_date: '', storage_location: '' },
      ],
    });
  });

  it('builds the receive body, dropping blank optionals', () => {
    const payload = toReceivePayload({
      lines: [
        {
          item_id: 'i1',
          batch_number: 'LOT-A',
          expiry_date: '2030-01-01',
          manufacturing_date: '',
          storage_location: '',
        },
        {
          item_id: 'i2',
          batch_number: 'LOT-B',
          expiry_date: '2031-06-01',
          manufacturing_date: '2026-06-01',
          storage_location: 'Cold Room A',
        },
      ],
    });
    expect(payload).toEqual({
      lines: [
        { item_id: 'i1', batch_number: 'LOT-A', expiry_date: '2030-01-01' },
        {
          item_id: 'i2',
          batch_number: 'LOT-B',
          expiry_date: '2031-06-01',
          manufacturing_date: '2026-06-01',
          storage_location: 'Cold Room A',
        },
      ],
    });
  });
});
