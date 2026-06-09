import { z } from 'zod';

/** Units of measure offered in the form (UI_SPECIFICATION §6.3.3). */
export const ITEM_UNITS = ['kg', 'pcs', 'L', 'm', 'set'] as const;

const DECIMAL_RE = /^\d+(\.\d+)?$/;

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
