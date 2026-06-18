import { z } from 'zod';

const DECIMAL_RE = /^\d+(\.\d+)?$/;

const lineSchema = z.object({
  item_id: z.string().min(1, 'Pick an item'),
  quantity: z
    .string()
    .trim()
    .min(1, 'Qty required')
    .refine((v) => DECIMAL_RE.test(v) && Number(v) > 0, 'Qty must be greater than 0'),
  // Optional — blank lets the Backend price it from the vendor's active term.
  unit_price: z
    .string()
    .trim()
    .refine((v) => v === '' || DECIMAL_RE.test(v), 'Price must be a non-negative number'),
});

export const poCreateSchema = z.object({
  vendor_id: z.string().min(1, 'Pick a vendor'),
  expected_delivery_date: z.string(),
  notes: z.string().trim().max(1000, 'Keep notes under 1000 characters'),
  items: z.array(lineSchema).min(1, 'Add at least one line item'),
});

export type PoFormValues = z.infer<typeof poCreateSchema>;
export type PoLineValues = z.infer<typeof lineSchema>;

/* ---- Receive (one or more lots per line) — Backend §9.8, multi-lot (#10) ---- */

const receiveLineSchema = z
  .object({
    item_id: z.string(),
    batch_number: z
      .string()
      .trim()
      .min(1, 'Batch number required')
      .max(64, 'Keep the batch number under 64 characters'),
    expiry_date: z.string().min(1, 'Expiry date required'),
    // Quantity for this lot. A PO line split across lots must allocate its
    // full quantity; the form seeds a single lot with the whole line qty.
    quantity: z
      .string()
      .trim()
      .min(1, 'Qty required')
      .refine((v) => DECIMAL_RE.test(v) && Number(v) > 0, 'Qty must be greater than 0'),
    // Optional — blank means "not recorded".
    manufacturing_date: z.string(),
    storage_location: z.string().trim().max(120, 'Keep the location under 120 characters'),
  })
  .refine(
    (l) => l.manufacturing_date === '' || l.expiry_date >= l.manufacturing_date,
    { message: 'Expiry must be on or after the manufacturing date', path: ['expiry_date'] },
  );

export const poReceiveSchema = z.object({
  lines: z.array(receiveLineSchema).min(1, 'A purchase order must have at least one line'),
});

export type PoReceiveValues = z.infer<typeof poReceiveSchema>;
export type PoReceiveLineValues = z.infer<typeof receiveLineSchema>;

export const EMPTY_LINE: PoLineValues = { item_id: '', quantity: '', unit_price: '' };

export const EMPTY_PO: PoFormValues = {
  vendor_id: '',
  expected_delivery_date: '',
  notes: '',
  items: [{ ...EMPTY_LINE }],
};
