import { FormEvent, useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';

const LoginPage = () => {
  const { login, status, error, isAuthenticated } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();
  const location = useLocation();

  const fromLocation = (location.state as {
    from?: { pathname?: string; search?: string; hash?: string };
  } | undefined)?.from;
  const fromPathname = fromLocation?.pathname ?? '/dashboards/campaigns';
  const fromSearch = fromLocation?.search ?? '';
  const fromHash = fromLocation?.hash ?? '';
  const from = `${fromPathname}${fromSearch}${fromHash}`;

  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [from, isAuthenticated, navigate]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch {
      // handled via auth state
    }
  };

  return (
    <div className="auth-shell">
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <h1>ADinsights</h1>
        <p className="muted">Sign in to access client dashboards.</p>
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          autoComplete="email"
        />
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          autoComplete="current-password"
        />
        <div className="auth-links">
          <Link to="/password-reset">Forgot your password?</Link>
        </div>
        {error ? <p className="status-message error">{error}</p> : null}
        <button type="submit" disabled={status === 'authenticating'} className="button primary">
          {status === 'authenticating' ? 'Signing in…' : 'Sign In'}
        </button>
      </form>
    </div>
  );
};

export default LoginPage;
