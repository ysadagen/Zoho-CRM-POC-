import { z } from 'zod';

const DECIMAL_RE = /^\d+(\.\d+)?$/;

const lineSchema = z.object({
  item_id: z.string().min(1, 'Pick an item'),
  quantity: z
    .string()
    .trim()
    .min(1, 'Qty required')
    .refine((v) => DECIMAL_RE.test(v) && Number(v) > 0, 'Qty must be greater than 0'),
  // Optional — blank lets the Backend use the item's catalog price.
  unit_price: z
    .string()
    .trim()
    .refine((v) => v === '' || DECIMAL_RE.test(v), 'Price must be a non-negative number'),
});

export const soCreateSchema = z.object({
  customer_id: z.string().min(1, 'Pick a customer'),
  expected_delivery_date: z.string(),
  notes: z.string().trim().max(1000, 'Keep notes under 1000 characters'),
  items: z.array(lineSchema).min(1, 'Add at least one line item'),
});

export type SoFormValues = z.infer<typeof soCreateSchema>;
export type SoLineValues = z.infer<typeof lineSchema>;

export const EMPTY_LINE: SoLineValues = { item_id: '', quantity: '', unit_price: '' };

export const EMPTY_SO: SoFormValues = {
  customer_id: '',
  expected_delivery_date: '',
  notes: '',
  items: [{ ...EMPTY_LINE }],
};
