import { describe, it, expect } from 'vitest';

import type { Item, StockMovement } from '@/types/api.types';

import {
  itemStatusBadge,
  itemToEditValues,
  itemTypeBadge,
  parseIngredients,
  serializeIngredients,
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
    direction: 'IN',
    reason: 'PURCHASE',
    quantity: '100',
    signed_quantity: '100',
    stock_before: '0',
    stock_after: '100',
    reference_type: 'PURCHASE_ORDER',
    reference_id: 'po1',
    batch_id: null,
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
  const PHARMA_EMPTY = {
    storage_condition: '',
    shelf_life_days: '',
    material_classification: '',
    pharmacopoeia: '',
    is_hazardous: false,
    generic_name: '',
    brand_name: '',
    strength: '',
    dosage_form: '',
    pack_size: '',
    ingredients: '',
    container_specification: '',
    selling_price: '',
    license_number: '',
    registration_code: '',
    mrp: '',
    drug_schedule: '',
    is_prescription_required: false,
  };

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
    ...PHARMA_EMPTY,
  };

  it('includes only the filled optionals + the type-matched detail block', () => {
    const payload = toCreatePayload({ ...base, stock_quantity: '', reorder_threshold: '', description: '' });
    expect(payload).toEqual({
      sku: 'BOT-1L',
      name: '1L Bottle',
      type: 'FINISHED',
      category: 'Bottles',
      unit_of_measure: 'pcs',
      unit_price: '45',
      // FINISHED item → finished_detail (the boolean is always carried).
      finished_detail: { is_prescription_required: false },
    });
  });

  it('carries optionals + pharma fields through when present', () => {
    const payload = toCreatePayload({
      ...base,
      description: 'Round bottle',
      stock_quantity: '500',
      reorder_threshold: '100',
      storage_condition: 'COLD_CHAIN_2_8',
      shelf_life_days: '365',
      generic_name: 'Paracetamol',
      dosage_form: 'TABLET',
      mrp: '25.00',
      is_prescription_required: true,
    });
    expect(payload).toMatchObject({
      description: 'Round bottle',
      stock_quantity: '500',
      reorder_threshold: '100',
      storage_condition: 'COLD_CHAIN_2_8',
      shelf_life_days: 365,
      finished_detail: {
        generic_name: 'Paracetamol',
        dosage_form: 'TABLET',
        mrp: '25.00',
        is_prescription_required: true,
      },
    });
  });

  it('builds raw_detail for a RAW item', () => {
    const payload = toCreatePayload({
      ...base,
      type: 'RAW',
      material_classification: 'API',
      is_hazardous: true,
    });
    expect(payload.raw_detail).toEqual({ material_classification: 'API', is_hazardous: true });
    expect(payload).not.toHaveProperty('finished_detail');
  });
});

describe('toUpdatePayload', () => {
  const editBase = {
    name: 'New name',
    category: 'Bottles',
    description: '',
    unit_of_measure: 'kg' as const,
    reorder_threshold: '',
    unit_price: '12.50',
    storage_condition: '',
    shelf_life_days: '',
    material_classification: '',
    pharmacopoeia: '',
    is_hazardous: false,
    generic_name: '',
    brand_name: '',
    strength: '',
    dosage_form: '',
    pack_size: '',
    ingredients: '',
    container_specification: '',
    selling_price: '',
    license_number: '',
    registration_code: '',
    mrp: '',
    drug_schedule: '',
    is_prescription_required: false,
  };

  it('only sends PATCH-safe fields + the type-matched detail block', () => {
    const payload = toUpdatePayload(editBase, 'RAW');
    expect(payload).toEqual({
      name: 'New name',
      category: 'Bottles',
      unit_of_measure: 'kg',
      unit_price: '12.50',
      raw_detail: { is_hazardous: false },
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
      storage_condition: '',
      shelf_life_days: '',
      material_classification: '',
      pharmacopoeia: '',
      is_hazardous: false,
      generic_name: '',
      brand_name: '',
      strength: '',
      dosage_form: '',
      pack_size: '',
      ingredients: '',
      container_specification: '',
      selling_price: '',
      license_number: '',
      registration_code: '',
      mrp: '',
      drug_schedule: '',
      is_prescription_required: false,
    });
  });

  it('seeds the raw/finished detail block from the item', () => {
    const raw = itemToEditValues(
      item({ raw_detail: { material_classification: 'API', pharmacopoeia: 'IP', is_hazardous: true } }),
    );
    expect(raw.material_classification).toBe('API');
    expect(raw.is_hazardous).toBe(true);
  });

  it('falls back to a known unit when the Backend unit is unfamiliar', () => {
    expect(itemToEditValues(item({ unit_of_measure: 'dozen' })).unit_of_measure).toBe('kg');
  });
});

describe('parseIngredients', () => {
  it('parses a JSON object keyed by codes into readable lines', () => {
    const raw =
      '{"RM020":{"name":"Polypropylene","qty":2.5,"unit":"g"},"RM021":{"name":"Needle","qty":1,"unit":"piece"}}';
    expect(parseIngredients(raw)).toEqual([
      { name: 'Polypropylene', qty: '2.5', unit: 'g' },
      { name: 'Needle', qty: '1', unit: 'piece' },
    ]);
  });

  it('parses a JSON array form', () => {
    expect(parseIngredients('[{"name":"Paracetamol","qty":"500","unit":"mg"}]')).toEqual([
      { name: 'Paracetamol', qty: '500', unit: 'mg' },
    ]);
  });

  it('returns null for blank, non-JSON, or shapeless input (caller shows raw)', () => {
    expect(parseIngredients(null)).toBeNull();
    expect(parseIngredients('')).toBeNull();
    expect(parseIngredients('just a plain sentence')).toBeNull();
    expect(parseIngredients('{"x":{"qty":1}}')).toBeNull(); // no name → skipped → empty → null
  });
});

describe('serializeIngredients', () => {
  it('serializes named rows to a JSON array, dropping empty qty/unit + nameless rows', () => {
    const json = serializeIngredients([
      { name: 'Paracetamol', qty: '500', unit: 'mg' },
      { name: 'Coating', qty: '', unit: '' },
      { name: '', qty: '5', unit: 'mg' },
    ]);
    expect(JSON.parse(json)).toEqual([
      { name: 'Paracetamol', qty: '500', unit: 'mg' },
      { name: 'Coating' },
    ]);
  });

  it('round-trips through parseIngredients', () => {
    const lines = [{ name: 'API', qty: '10', unit: 'g' }];
    expect(parseIngredients(serializeIngredients(lines))).toEqual(lines);
  });

  it('returns an empty string when no row has a name', () => {
    expect(serializeIngredients([{ name: '  ', qty: '1', unit: 'g' }])).toBe('');
    expect(serializeIngredients([])).toBe('');
  });
});
