/**
 * App.jsx — React Router route configuration.
 *
 * Public routes:  /login, /register
 * Protected routes (wrapped in ProtectedRoute + AppLayout):
 *   /workspace        → WorkspacePage   (empty state / default)
 *   /workspace/:id    → WorkspaceDocPage (analysis + Q&A)
 *
 * Legacy redirects (for bookmarked URLs):
 *   /               → /workspace
 *   /documents      → /workspace
 *   /documents/:id  → /workspace/:id
 *   /query          → /workspace
 *
 * Any other unknown path redirects to /workspace.
 */

import { BrowserRouter, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';

import ProtectedRoute     from './components/ProtectedRoute';
import AppLayout          from './components/AppLayout';

import LoginPage          from './pages/LoginPage';
import RegisterPage       from './pages/RegisterPage';
import WorkspacePage      from './pages/WorkspacePage';
import WorkspaceDocPage   from './pages/WorkspaceDocPage';

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
              {/* Primary workspace routes */}
              <Route path="/workspace"     element={<WorkspacePage />} />
              <Route path="/workspace/:id" element={<WorkspaceDocPage />} />

              {/* Legacy redirects — preserve old bookmarked URLs */}
              <Route path="/"              element={<Navigate to="/workspace" replace />} />
              <Route path="/documents"     element={<Navigate to="/workspace" replace />} />
              <Route path="/documents/:id" element={<LegacyDocRedirect />} />
              <Route path="/query"         element={<Navigate to="/workspace" replace />} />
            </Route>
          </Route>

          {/* ── Fallback ── */}
          <Route path="*" element={<Navigate to="/workspace" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

/**
 * Redirect /documents/:id → /workspace/:id
 * Preserves the document ID so existing bookmarks open the right doc.
 */
function LegacyDocRedirect() {
  const { id } = useParams();
  return <Navigate to={`/workspace/${id}`} replace />;
}
