import { z } from 'zod';

import {
  DOSAGE_FORM_OPTIONS,
  DRUG_SCHEDULE_OPTIONS,
  MATERIAL_CLASSIFICATION_OPTIONS,
  PHARMACOPOEIA_OPTIONS,
  STORAGE_CONDITION_OPTIONS,
  type Option,
} from './pharma';

/** Units of measure offered in the form (UI_SPECIFICATION §6.3.3). */
export const ITEM_UNITS = ['kg', 'pcs', 'L', 'm', 'set'] as const;

const DECIMAL_RE = /^\d+(\.\d+)?$/;
const INTEGER_RE = /^\d+$/;

/** Required non-negative decimal entered as a string (Backend keeps Decimals as strings). */
const requiredDecimal = (label: string) =>
  z
    .string()
    .trim()
    .min(1, `${label} is required`)
    .refine((v) => DECIMAL_RE.test(v), `${label} must be a non-negative number`);

/** Optional non-negative decimal — empty string means "not set". */
const optionalDecimal = (label: string) =>
  z
    .string()
    .trim()
    .refine((v) => v === '' || DECIMAL_RE.test(v), `${label} must be a non-negative number`);

/** Optional non-negative whole number — empty string means "not set". */
const optionalInteger = (label: string) =>
  z
    .string()
    .trim()
    .refine((v) => v === '' || INTEGER_RE.test(v), `${label} must be a whole number`);

/** Select value that is either blank ("not set") or one of the enum options. */
const enumOrEmpty = (options: Option<string>[]) => {
  const valid = new Set(options.map((o) => o.value));
  return z.string().refine((v) => v === '' || valid.has(v), 'Pick a valid option');
};

/** Common-pharma fields (apply to both raw + finished). */
const commonPharmaFields = {
  storage_condition: enumOrEmpty(STORAGE_CONDITION_OPTIONS),
  shelf_life_days: optionalInteger('Shelf life'),
};

/** RAW-only detail fields (shown when type=RAW). */
const rawDetailFields = {
  material_classification: enumOrEmpty(MATERIAL_CLASSIFICATION_OPTIONS),
  pharmacopoeia: enumOrEmpty(PHARMACOPOEIA_OPTIONS),
  is_hazardous: z.boolean(),
};

/** FINISHED-only detail fields (shown when type=FINISHED). */
const finishedDetailFields = {
  generic_name: z.string().trim().max(255, 'Keep under 255 characters'),
  brand_name: z.string().trim().max(255, 'Keep under 255 characters'),
  strength: z.string().trim().max(64, 'Keep under 64 characters'),
  dosage_form: enumOrEmpty(DOSAGE_FORM_OPTIONS),
  pack_size: z.string().trim().max(64, 'Keep under 64 characters'),
  ingredients: z.string().trim().max(2000, 'Keep under 2000 characters'),
  container_specification: z.string().trim().max(255, 'Keep under 255 characters'),
  selling_price: optionalDecimal('Selling price'),
  license_number: z.string().trim().max(64, 'Keep under 64 characters'),
  registration_code: z.string().trim().max(64, 'Keep under 64 characters'),
  mrp: optionalDecimal('MRP'),
  drug_schedule: enumOrEmpty(DRUG_SCHEDULE_OPTIONS),
  is_prescription_required: z.boolean(),
};

/** Fields editable in BOTH create and edit (PATCH-safe per Backend §9.3). */
const editableFields = {
  name: z.string().trim().min(1, 'Name is required'),
  category: z
    .string()
    .trim()
    .min(1, 'Category is required')
    .max(64, 'Keep the category under 64 characters'),
  description: z.string().trim().max(500, 'Keep the description under 500 characters'),
  unit_of_measure: z.enum(ITEM_UNITS, { message: 'Pick a unit' }),
  reorder_threshold: optionalDecimal('Reorder threshold'),
  unit_price: requiredDecimal('Unit price'),
  standard_cost: optionalDecimal('Standard cost'),
  ...commonPharmaFields,
  ...rawDetailFields,
  ...finishedDetailFields,
};

/** Create adds the identity fields the Backend won't let you PATCH later. */
export const itemCreateSchema = z.object({
  sku: z.string().trim().min(1, 'SKU is required'),
  type: z.enum(['RAW', 'FINISHED'], { message: 'Pick a type' }),
  stock_quantity: optionalDecimal('Initial stock'),
  ...editableFields,
});

export const itemEditSchema = z.object(editableFields);

export type ItemCreateValues = z.infer<typeof itemCreateSchema>;
export type ItemEditValues = z.infer<typeof itemEditSchema>;
