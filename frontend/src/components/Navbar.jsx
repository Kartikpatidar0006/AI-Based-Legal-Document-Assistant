/**
 * Navbar — persistent top navigation bar.
 *
 * Left  : logo mark + app name
 * Centre: nav links (Dashboard, Ask a Question)
 * Right : user's business_name + Logout button
 */

import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <header className="navbar">
      <div className="navbar__inner">
        {/* ── Brand ──────────────────────────────────────────────── */}
        <div className="navbar__brand">
          <span className="navbar__logo-mark" aria-hidden="true">⚖</span>
          <span className="navbar__app-name">LegalEase <em>AI</em></span>
        </div>

        {/* ── Nav links ──────────────────────────────────────────── */}
        <nav className="navbar__links" aria-label="Main navigation">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              'navbar__link' + (isActive ? ' navbar__link--active' : '')
            }
          >
            Dashboard
          </NavLink>
          <NavLink
            to="/query"
            className={({ isActive }) =>
              'navbar__link' + (isActive ? ' navbar__link--active' : '')
            }
          >
            Ask a Question
          </NavLink>
        </nav>

        {/* ── User / logout ──────────────────────────────────────── */}
        <div className="navbar__user">
          {user && (
            <span className="navbar__business-name" title={user.email}>
              {user.business_name || user.name}
            </span>
          )}
          <button
            id="logout-btn"
            className="btn btn--ghost btn--sm"
            onClick={handleLogout}
          >
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}
