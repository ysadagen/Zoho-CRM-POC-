import { useMutation, type UseMutationResult } from '@tanstack/react-query';

import { useAuth } from '@/auth/useAuth';
import { logger } from '@/lib/logger';
import type { User } from '@/types/api.types';

import { updateProfile } from '../api/settings.api';

/** Updates the signed-in user's name and syncs it into the auth session. */
export function useUpdateProfile(userId: string): UseMutationResult<User, unknown, string> {
  const { updateUser } = useAuth();
  return useMutation({
    mutationFn: (fullName: string) => updateProfile(userId, { full_name: fullName }),
    onSuccess: (user) => {
      logger.info('settings.profile.update', { userId: user.id });
      updateUser(user);
    },
  });
}
