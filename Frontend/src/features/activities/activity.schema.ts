import { z } from 'zod';

import { ActivityType } from '@/types/enums';

const ACTIVITY_TYPES = Object.values(ActivityType) as [ActivityType, ...ActivityType[]];

/** Log-activity form. `occurred_at` is a `datetime-local` string (no timezone). */
export const activitySchema = z.object({
  type: z.enum(ACTIVITY_TYPES, { required_error: 'Type is required' }),
  occurred_at: z
    .string()
    .trim()
    .min(1, 'When is required')
    .refine((value) => !Number.isNaN(new Date(value).getTime()), 'Enter a valid date and time')
    .refine((value) => new Date(value).getTime() <= Date.now(), 'Cannot be in the future'),
  duration_minutes: z
    .string()
    .trim()
    .optional()
    .refine(
      (value) => !value || (Number.isInteger(Number(value)) && Number(value) > 0),
      'Enter a positive whole number',
    ),
  remarks: z.string().trim().optional(),
});

export type ActivityValues = z.infer<typeof activitySchema>;

export const EMPTY_ACTIVITY: ActivityValues = {
  type: ActivityType.VISIT,
  occurred_at: '',
  duration_minutes: '',
  remarks: '',
};
