import { apiPost } from '@/lib/api/client';
import type { LoginRequest, LoginResponse, RegisterRequest, User } from '@/types/api.types';

const AUTH_BASE = '/api/v1/auth';

/** POST /auth/login → JWT + the user payload. 401 INVALID_CREDENTIALS on failure. */
export function login(credentials: LoginRequest): Promise<LoginResponse> {
  return apiPost<LoginResponse, LoginRequest>(`${AUTH_BASE}/login`, credentials);
}

/** POST /auth/register → the created user (no token). 409 EMAIL_ALREADY_REGISTERED on conflict. */
export function register(data: RegisterRequest): Promise<User> {
  return apiPost<User, RegisterRequest>(`${AUTH_BASE}/register`, data);
}
