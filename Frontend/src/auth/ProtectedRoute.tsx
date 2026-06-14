import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { routes } from '@/app/routes';

import { useAuth } from './useAuth';

/** Gate for the authenticated app. Preserves `from` so login can bounce back. */
export function ProtectedRoute(): JSX.Element {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to={routes.login} state={{ from: location }} replace />;
  }
  return <Outlet />;
}
