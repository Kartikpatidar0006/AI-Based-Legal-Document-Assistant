/**
 * App.jsx — React Router route configuration.
 *
 * Public routes:  /login, /register
 * Protected routes (wrapped in ProtectedRoute + AppLayout):
 *   /           → DashboardPage
 *   /documents/:id  → DocumentAnalysisPage
 *   /query      → QueryPage
 *
 * Any unknown path redirects to / (which then redirects to /login if not authed).
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';

import ProtectedRoute          from './components/ProtectedRoute';
import AppLayout               from './components/AppLayout';

import LoginPage               from './pages/LoginPage';
import RegisterPage            from './pages/RegisterPage';
import DashboardPage           from './pages/DashboardPage';
import DocumentAnalysisPage    from './pages/DocumentAnalysisPage';
import QueryPage               from './pages/QueryPage';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* ── Public ── */}
          <Route path="/login"    element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* ── Protected (require login, render inside AppLayout) ── */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/"                  element={<DashboardPage />} />
              <Route path="/documents/:id"     element={<DocumentAnalysisPage />} />
              <Route path="/query"             element={<QueryPage />} />
            </Route>
          </Route>

          {/* ── Fallback ── */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
