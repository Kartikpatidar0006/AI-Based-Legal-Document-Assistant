/**
 * src/context/AuthContext.jsx
 * Provides authentication state and actions to the entire app.
 *
 * On mount: checks localStorage for a saved token + user and restores them.
 * login / register: call the API, persist the result, update state.
 * logout: clears localStorage and state, redirects to /login.
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { loginUser, registerUser } from '../api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]   = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true); // true while bootstrapping

  // ── Bootstrap from localStorage ────────────────────────────────────────────
  useEffect(() => {
    try {
      const savedToken = localStorage.getItem('access_token');
      const savedUser  = localStorage.getItem('user');
      if (savedToken && savedUser) {
        setToken(savedToken);
        setUser(JSON.parse(savedUser));
      }
    } catch {
      // corrupted storage — start fresh
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
    } finally {
      setLoading(false);
    }
  }, []);

  // ── Persist helpers ─────────────────────────────────────────────────────────
  function persist(accessToken, userData) {
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('user', JSON.stringify(userData));
    setToken(accessToken);
    setUser(userData);
  }

  // ── Actions ─────────────────────────────────────────────────────────────────
  const login = useCallback(async (email, password) => {
    const data = await loginUser({ email, password }); // throws on error
    persist(data.access_token, data.user);
    return data;
  }, []);

  const register = useCallback(async (name, email, password, business_name) => {
    const data = await registerUser({ name, email, password, business_name });
    persist(data.access_token, data.user);
    return data;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
  }, []);

  const value = {
    user,
    token,
    loading,
    isAuthenticated: !!token,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Hook to consume auth context — throws if used outside <AuthProvider>. */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
