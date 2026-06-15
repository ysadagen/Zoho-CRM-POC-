import { describe, it, expect } from 'vitest';

import { EMPTY_BATCH } from './batch.schema';
import { BATCH_STATUS_OPTIONS, batchStatusBadge, toBatchCreatePayload } from './batch.transform';

describe('batchStatusBadge', () => {
  it('maps each status to its badge', () => {
    expect(batchStatusBadge('QUARANTINE')).toEqual({ variant: 'warn', label: 'Quarantine' });
    expect(batchStatusBadge('RELEASED')).toEqual({ variant: 'success', label: 'Released' });
    expect(batchStatusBadge('EXPIRED')).toEqual({ variant: 'danger', label: 'Expired' });
    expect(batchStatusBadge('REJECTED')).toEqual({ variant: 'danger', label: 'Rejected' });
    expect(batchStatusBadge('RECALLED')).toEqual({ variant: 'danger', label: 'Recalled' });
  });
});

describe('BATCH_STATUS_OPTIONS', () => {
  it('lists every status with a label', () => {
    expect(BATCH_STATUS_OPTIONS.map((o) => o.value)).toEqual([
      'QUARANTINE',
      'RELEASED',
      'EXPIRED',
      'REJECTED',
      'RECALLED',
    ]);
    expect(BATCH_STATUS_OPTIONS.every((o) => o.label.length > 0)).toBe(true);
  });
});

describe('toBatchCreatePayload', () => {
  it('drops blank optionals, keeping the required fields + status', () => {
    const payload = toBatchCreatePayload({
      ...EMPTY_BATCH,
      item_id: 'i1',
      batch_number: 'LOT-A',
      expiry_date: '2030-01-01',
      quantity: '40',
    });
    expect(payload).toEqual({
      item_id: 'i1',
      batch_number: 'LOT-A',
      expiry_date: '2030-01-01',
      quantity: '40',
      batch_status: 'QUARANTINE',
    });
  });

  it('carries the optionals through when present', () => {
    const payload = toBatchCreatePayload({
      item_id: 'i1',
      batch_number: 'LOT-A',
      expiry_date: '2030-01-01',
      manufacturing_date: '2026-01-01',
      quantity: '40',
      unit_cost: '12.50',
      storage_location: 'Cold Room A',
      batch_status: 'RELEASED',
    });
    expect(payload).toMatchObject({
      manufacturing_date: '2026-01-01',
      unit_cost: '12.50',
      storage_location: 'Cold Room A',
      batch_status: 'RELEASED',
    });
  });
});
