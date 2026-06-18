import { z } from 'zod';

const DECIMAL_RE = /^\d+(\.\d+)?$/;

export const batchCreateSchema = z
  .object({
    item_id: z.string().min(1, 'Pick an item'),
    batch_number: z
      .string()
      .trim()
      .min(1, 'Batch number is required')
      .max(64, 'Keep the batch number under 64 characters'),
    expiry_date: z.string().min(1, 'Expiry date is required'),
    manufacturing_date: z.string(),
    quantity: z
      .string()
      .trim()
      .min(1, 'Quantity is required')
      .refine((v) => DECIMAL_RE.test(v) && Number(v) > 0, 'Quantity must be greater than 0'),
    unit_cost: z
      .string()
      .trim()
      .refine((v) => v === '' || DECIMAL_RE.test(v), 'Unit cost must be a non-negative number'),
    storage_location: z.string().trim().max(120, 'Keep the location under 120 characters'),
    batch_status: z.enum(['QUARANTINE', 'RELEASED', 'EXPIRED', 'REJECTED', 'RECALLED']),
  })
  .refine(
    (v) => v.manufacturing_date === '' || v.expiry_date >= v.manufacturing_date,
    { message: 'Expiry must be on or after the manufacturing date', path: ['expiry_date'] },
  );

export type BatchFormValues = z.infer<typeof batchCreateSchema>;

export const EMPTY_BATCH: BatchFormValues = {
  item_id: '',
  batch_number: '',
  expiry_date: '',
  manufacturing_date: '',
  quantity: '',
  unit_cost: '',
  storage_location: '',
  batch_status: 'QUARANTINE',
};
