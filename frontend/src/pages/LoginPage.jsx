/**
 * LoginPage — two-column split layout.
 * Left panel: dark navy, live product-moment artifact (mock risk card).
 * Right panel: white, the actual login form.
 *
 * API calls, routing, and AuthContext usage are unchanged.
 * On success: stores token/user via AuthContext and navigates to Dashboard.
 */

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate  = useNavigate();

  const [form, setForm]       = useState({ email: '', password: '' });
  const [error, setError]     = useState('');
  const [loading, setLoading] = useState(false);

  function handleChange(e) {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setError('');
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await login(form.email, form.password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.message || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-split">

      {/* ── Left panel — product-moment ─────────────────────────────────── */}
      <div className="login-panel" aria-hidden="true">
        {/* Wordmark */}
        <div className="login-panel__wordmark">
          <div className="login-panel__logo">⚖</div>
          <div className="login-panel__app-name">
            LegalEase AI
            <em>for Indian businesses</em>
          </div>
        </div>

        {/* Mock artifact — a real analysis output, rendered as UI */}
        <div className="login-artifact">
          <div className="login-artifact__header">
            <span className="login-artifact__doc-name">Vendor Services Agreement.pdf</span>
            <span className="login-artifact__badge login-artifact__badge--analyzed">Analyzed</span>
          </div>
          <div className="login-artifact__body">
            <div className="login-artifact__row login-artifact__row--high">
              <span className="login-artifact__clause-name">Non-Compete</span>
              <span className="login-artifact__clause-meta">3 yrs · All of India</span>
              <span className="login-artifact__risk login-artifact__risk--high">High</span>
            </div>
            <div className="login-artifact__row login-artifact__row--medium">
              <span className="login-artifact__clause-name">Payment Terms</span>
              <span className="login-artifact__clause-meta">Net 90 days</span>
              <span className="login-artifact__risk login-artifact__risk--medium">Medium</span>
            </div>
            <div className="login-artifact__row login-artifact__row--high">
              <span className="login-artifact__clause-name">Liability Cap</span>
              <span className="login-artifact__clause-meta">₹50,000 ceiling</span>
              <span className="login-artifact__risk login-artifact__risk--high">High</span>
            </div>
          </div>
        </div>

        {/* Tagline */}
        <p className="login-panel__tagline">
          Know what you're signing<br />before you sign it.
        </p>
      </div>

      {/* ── Right panel — the login form ────────────────────────────────── */}
      <div className="login-form-col">
        <h1 className="login-form-col__heading">Sign in</h1>
        <p className="login-form-col__sub">
          Access your documents and risk analysis dashboard.
        </p>

        <form id="login-form" className="auth-form" onSubmit={handleSubmit} noValidate>
          {error && (
            <div className="form-error" role="alert">
              {error}
            </div>
          )}

          <div className="form-group">
            <label className="form-label" htmlFor="login-email">Email address</label>
            <input
              id="login-email"
              className="form-input"
              type="email"
              name="email"
              autoComplete="email"
              required
              placeholder="you@company.com"
              value={form.email}
              onChange={handleChange}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="login-password">Password</label>
            <input
              id="login-password"
              className="form-input"
              type="password"
              name="password"
              autoComplete="current-password"
              required
              placeholder="••••••••"
              value={form.password}
              onChange={handleChange}
            />
          </div>

          <button
            id="login-submit-btn"
            type="submit"
            className="btn btn--primary btn--full btn--lg"
            disabled={loading}
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <p className="auth-card__footer">
          Don't have an account?{' '}
          <Link to="/register" className="auth-card__link">Create one</Link>
        </p>
      </div>

    </div>
  );
}
