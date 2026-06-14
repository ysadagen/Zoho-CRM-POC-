import { z } from 'zod';

/** One schema for create + edit — all fields but the company name are optional. */
export const customerSchema = z.object({
  company_name: z.string().trim().min(1, 'Company name is required'),
  contact_person: z.string().trim(),
  email: z.string().trim().email('Enter a valid email').or(z.literal('')),
  phone: z.string().trim(),
  customer_code: z.string().trim(),
  gstin: z.string().trim(),
  is_privileged: z.boolean(),
});

export type CustomerValues = z.infer<typeof customerSchema>;

export const EMPTY_CUSTOMER: CustomerValues = {
  company_name: '',
  contact_person: '',
  email: '',
  phone: '',
  customer_code: '',
  gstin: '',
  is_privileged: false,
};
