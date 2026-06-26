import { z } from 'zod';

import { CompetitiveRiskLevel, CustomerType } from '@/types/enums';

const GSTIN_RE = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;

export const customerSchema = z.object({
  company_name: z.string().trim().min(1, 'Company name is required'),
  contact_person: z.string().trim(),
  email: z.string().trim().email('Enter a valid email').or(z.literal('')),
  phone: z.string().trim(),
  customer_code: z.string().trim(),
  gstin: z.string().trim().refine((v) => v === '' || GSTIN_RE.test(v), 'Enter a valid 15-character GSTIN'),
  is_privileged: z.boolean(),
  customer_type: z.enum([CustomerType.DEALER, CustomerType.SUB_DEALER, CustomerType.RETAILER]),
  competitive_risk_level: z.enum([
    CompetitiveRiskLevel.NONE,
    CompetitiveRiskLevel.LOW,
    CompetitiveRiskLevel.MEDIUM,
    CompetitiveRiskLevel.HIGH,
  ]),
  address: z.string().trim().max(2000, 'Keep under 2000 characters'),
  state: z.string().trim().max(120, 'Keep under 120 characters'),
  city: z.string().trim().max(120, 'Keep under 120 characters'),
  district: z.string().trim().max(120, 'Keep under 120 characters'),
  pincode: z.string().trim().max(20, 'Keep under 20 characters'),
  notes: z.string().trim().max(2000, 'Keep under 2000 characters'),
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
  customer_type: CustomerType.RETAILER,
  competitive_risk_level: CompetitiveRiskLevel.NONE,
  address: '',
  state: '',
  city: '',
  district: '',
  pincode: '',
  notes: '',
};
