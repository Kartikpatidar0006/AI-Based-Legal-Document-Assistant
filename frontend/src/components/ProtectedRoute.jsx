/**
 * ProtectedRoute — wraps routes that require authentication.
 * Redirects to /login if the user is not authenticated.
 * Shows nothing while the auth state is still bootstrapping from localStorage.
 */

import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute() {
  const { isAuthenticated, loading } = useAuth();

  // Still reading from localStorage — don't flash a redirect
  if (loading) return null;

  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
}
