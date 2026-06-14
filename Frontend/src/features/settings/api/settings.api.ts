import { apiPatch } from '@/lib/api/client';
import type { User, UserUpdateRequest } from '@/types/api.types';

const USERS = '/api/v1/users';

/** Self-service profile update. A non-admin user may only change `full_name`. */
export function updateProfile(userId: string, body: UserUpdateRequest): Promise<User> {
  return apiPatch<User, UserUpdateRequest>(`${USERS}/${userId}`, body);
}
