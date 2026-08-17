/**
 * RegisterPage — new user registration form.
 * Collects: name, email, password, business_name.
 *
 * On success: stores token/user via AuthContext, navigates to Dashboard.
 * On failure: shows the FastAPI error message inline.
 */

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate     = useNavigate();

  const [form, setForm] = useState({
    name: '',
    email: '',
    password: '',
    business_name: '',
  });
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
      await register(form.name, form.email, form.password, form.business_name);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.message || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card auth-card--wide">
        <div className="auth-card__brand">
          <span className="auth-card__logo" aria-hidden="true">⚖</span>
          <h1 className="auth-card__title">LegalEase AI</h1>
          <p className="auth-card__subtitle">Create your account</p>
        </div>

        <form id="register-form" className="auth-form" onSubmit={handleSubmit} noValidate>
          {error && (
            <div className="form-error" role="alert">
              {error}
            </div>
          )}

          <div className="form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="reg-name">Full name</label>
              <input
                id="reg-name"
                className="form-input"
                type="text"
                name="name"
                autoComplete="name"
                required
                placeholder="Priya Sharma"
                value={form.name}
                onChange={handleChange}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="reg-business">Business name</label>
              <input
                id="reg-business"
                className="form-input"
                type="text"
                name="business_name"
                autoComplete="organization"
                required
                placeholder="Sharma & Associates"
                value={form.business_name}
                onChange={handleChange}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="reg-email">Email address</label>
            <input
              id="reg-email"
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
            <label className="form-label" htmlFor="reg-password">Password</label>
            <input
              id="reg-password"
              className="form-input"
              type="password"
              name="password"
              autoComplete="new-password"
              required
              placeholder="Minimum 8 characters"
              minLength={8}
              value={form.password}
              onChange={handleChange}
            />
          </div>

          <button
            id="register-submit-btn"
            type="submit"
            className="btn btn--primary btn--full"
            disabled={loading}
          >
            {loading ? 'Creating account…' : 'Create Account'}
          </button>
        </form>

        <p className="auth-card__footer">
          Already have an account?{' '}
          <Link to="/login" className="auth-card__link">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
