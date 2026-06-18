import { z } from 'zod';

import { DealerPotential, LeadSource, LeadStage } from '@/types/enums';

const SOURCES = Object.values(LeadSource) as [LeadSource, ...LeadSource[]];
const POTENTIALS = Object.values(DealerPotential) as [DealerPotential, ...DealerPotential[]];

/** Create + edit form. `assigned_to_user_id` is set from the session, not the
 *  form (a rep owns the leads they create). Optional fields are blank strings
 *  in the form and dropped from the payload. */
export const leadSchema = z.object({
  contact_name: z.string().trim().min(1, 'Contact name is required'),
  source: z.enum(SOURCES),
  phone: z.string().trim(),
  email: z.string().trim().email('Enter a valid email').or(z.literal('')),
  estimated_budget: z
    .string()
    .trim()
    .refine((v) => v === '' || (!Number.isNaN(Number(v)) && Number(v) >= 0), 'Enter a valid amount'),
  dealer_potential: z.enum(POTENTIALS).or(z.literal('')),
  required_by_date: z.string().trim(),
  state: z.string().trim(),
  district: z.string().trim(),
  city: z.string().trim(),
  pincode: z.string().trim(),
  notes: z.string().trim(),
});

export type LeadValues = z.infer<typeof leadSchema>;

export const EMPTY_LEAD: LeadValues = {
  contact_name: '',
  source: LeadSource.FIELD_VISIT,
  phone: '',
  email: '',
  estimated_budget: '',
  dealer_potential: '',
  required_by_date: '',
  state: '',
  district: '',
  city: '',
  pincode: '',
  notes: '',
};

/** Stage transition. WON requires a value; LOST requires a reason — enforced
 *  here so the modal surfaces a clean message before hitting the API. */
export const transitionSchema = z
  .object({
    to_stage: z.enum([LeadStage.QUALIFICATION, LeadStage.NEGOTIATION, LeadStage.WON, LeadStage.LOST]),
    remark: z.string().trim(),
    won_value: z.string().trim(),
    lost_reason: z.string().trim(),
  })
  .superRefine((v, ctx) => {
    if (v.to_stage === LeadStage.WON) {
      const n = Number(v.won_value);
      if (v.won_value === '' || Number.isNaN(n) || n <= 0) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['won_value'], message: 'Won value is required' });
      }
    }
    if (v.to_stage === LeadStage.LOST && v.lost_reason === '') {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['lost_reason'], message: 'Lost reason is required' });
    }
  });

export type TransitionValues = z.infer<typeof transitionSchema>;
