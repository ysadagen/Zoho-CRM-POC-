import { createContext } from 'react';

import type { LoginRequest, RegisterRequest, User } from '@/types/api.types';

export interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  /** Registers a new user, then logs them in (the Backend register has no token). */
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
  /** Replaces the cached + persisted user (e.g. after a profile edit). */
  updateUser: (user: User) => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
