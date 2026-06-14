import { z } from 'zod';

export const editNameSchema = z.object({
  full_name: z.string().trim().min(1, 'Name is required').max(120, 'Keep it under 120 characters'),
});

export type EditNameValues = z.infer<typeof editNameSchema>;
