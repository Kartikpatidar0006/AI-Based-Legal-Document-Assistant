/**
 * LoginPage — email + password login form.
 *
 * On success: stores token/user via AuthContext and navigates to Dashboard.
 * On failure: shows the error message returned by FastAPI.
 */

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate  = useNavigate();

  const [form, setForm]     = useState({ email: '', password: '' });
  const [error, setError]   = useState('');
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
    <div className="auth-page">
      <div className="auth-card">
        {/* Brand mark */}
        <div className="auth-card__brand">
          <span className="auth-card__logo" aria-hidden="true">⚖</span>
          <h1 className="auth-card__title">LegalEase AI</h1>
          <p className="auth-card__subtitle">Sign in to your account</p>
        </div>

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
            className="btn btn--primary btn--full"
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
