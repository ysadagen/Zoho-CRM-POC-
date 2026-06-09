import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { configureAuthFailureHandler, configureAuthTokenSource } from '@/lib/api/client';
import { logger } from '@/lib/logger';
import type { LoginRequest, RegisterRequest, User } from '@/types/api.types';

import { AuthContext, type AuthContextValue } from './AuthContext';
import * as authApi from './auth.api';
import { clearSession, getSession, getToken, setSession } from './token-storage';

function persistUser(user: User): void {
  const session = getSession();
  if (session) setSession({ ...session, user });
}

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(() => getSession()?.user ?? null);

  // Wire the api client to this session: it pulls the bearer via getToken, and
  // on a session-expiry 401 it clears state and routes to login.
  useEffect(() => {
    configureAuthTokenSource(getToken);
    configureAuthFailureHandler(() => {
      clearSession();
      setUser(null);
      navigate(`${routes.login}?reason=expired`, { replace: true });
    });
  }, [navigate]);

  const login = useCallback(async (credentials: LoginRequest) => {
    const res = await authApi.login(credentials);
    setSession({
      token: res.access_token,
      expiresAt: Date.now() + res.expires_in * 1000,
      user: res.user,
    });
    setUser(res.user);
    logger.info('auth.login', { userId: res.user.id });
  }, []);

  const register = useCallback(
    async (data: RegisterRequest) => {
      await authApi.register(data);
      await login({ email: data.email, password: data.password });
    },
    [login],
  );

  const logout = useCallback(() => {
    clearSession();
    setUser(null);
    logger.info('auth.logout');
    navigate(routes.login, { replace: true });
  }, [navigate]);

  const updateUser = useCallback((updated: User) => {
    persistUser(updated);
    setUser(updated);
    logger.info('auth.user.updated', { userId: updated.id });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isAuthenticated: user !== null, login, register, logout, updateUser }),
    [user, login, register, logout, updateUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
