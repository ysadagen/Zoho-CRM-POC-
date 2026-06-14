import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import type { User } from '@/types/api.types';

import { AuthContext, type AuthContextValue } from './AuthContext';
import { ProtectedRoute } from './ProtectedRoute';

const USER: User = {
  id: 'u',
  email: 'e@x.com',
  full_name: 'F L',
  is_admin: false,
  is_active: true,
  created_at: '',
  updated_at: '',
};

function renderGuard(authed: boolean) {
  const value: AuthContextValue = {
    user: authed ? USER : null,
    isAuthenticated: authed,
    login: async () => {},
    register: async () => {},
    logout: () => {},
    updateUser: () => {},
  };
  return render(
    <AuthContext.Provider value={value}>
      <MemoryRouter
        initialEntries={['/secret']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/secret" element={<div>secret content</div>} />
          </Route>
          <Route path="/login" element={<div>login screen</div>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe('ProtectedRoute', () => {
  it('renders the outlet when authenticated', () => {
    renderGuard(true);
    expect(screen.getByText('secret content')).toBeInTheDocument();
  });

  it('redirects to login when unauthenticated', () => {
    renderGuard(false);
    expect(screen.getByText('login screen')).toBeInTheDocument();
  });
});
