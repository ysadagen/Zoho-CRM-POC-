import { z } from 'zod';

/** One schema for create + edit — only the vendor name is required. */
export const vendorSchema = z.object({
  vendor_name: z.string().trim().min(1, 'Vendor name is required'),
  contact_person: z.string().trim(),
  email: z.string().trim().email('Enter a valid email').or(z.literal('')),
  phone: z.string().trim(),
  vendor_code: z.string().trim(),
  gstin: z.string().trim(),
});

export type VendorValues = z.infer<typeof vendorSchema>;

export const EMPTY_VENDOR: VendorValues = {
  vendor_name: '',
  contact_person: '',
  email: '',
  phone: '',
  vendor_code: '',
  gstin: '',
};

const DECIMAL_RE = /^\d+(\.\d+)?$/;

/** Vendor-item pricing term. Dates are `YYYY-MM-DD` strings from date inputs. */
export const vendorTermSchema = z.object({
  item_id: z.string().min(1, 'Pick an item'),
  rate: z
    .string()
    .trim()
    .min(1, 'Rate is required')
    .refine((v) => DECIMAL_RE.test(v), 'Rate must be a non-negative number'),
  discount_percent: z
    .string()
    .trim()
    .refine((v) => v === '' || (DECIMAL_RE.test(v) && Number(v) <= 100), 'Discount must be 0–100'),
  effective_from: z.string().min(1, 'Start date is required'),
  effective_to: z.string(),
});

export type VendorTermValues = z.infer<typeof vendorTermSchema>;

export const EMPTY_TERM: VendorTermValues = {
  item_id: '',
  rate: '',
  discount_percent: '',
  effective_from: '',
  effective_to: '',
};
