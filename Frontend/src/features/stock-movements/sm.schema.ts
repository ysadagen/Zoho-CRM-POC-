import { z } from 'zod';

const DECIMAL_RE = /^\d+(\.\d+)?$/;

/** Manual adjustment — the only write to the append-only ledger. */
export const adjustmentSchema = z.object({
  item_id: z.string().min(1, 'Pick an item'),
  direction: z.enum(['IN', 'OUT']),
  quantity: z
    .string()
    .trim()
    .min(1, 'Quantity required')
    .refine((v) => DECIMAL_RE.test(v) && Number(v) > 0, 'Quantity must be greater than 0'),
  // §5 non-negotiable: accountability gate — a real reason, min 10 chars.
  remarks: z.string().trim().min(10, 'Add a reason of at least 10 characters'),
  // Optional lot (#8) — blank adjusts only the item aggregate.
  batch_id: z.string(),
});

export type AdjustmentValues = z.infer<typeof adjustmentSchema>;

export const EMPTY_ADJUSTMENT: AdjustmentValues = {
  item_id: '',
  direction: 'IN',
  quantity: '',
  remarks: '',
  batch_id: '',
};
