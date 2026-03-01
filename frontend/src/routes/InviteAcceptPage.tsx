import { FormEvent, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import apiClient from '../lib/apiClient';

type SubmitStatus = 'idle' | 'submitting' | 'success' | 'error';

const InviteAcceptPage = () => {
  const [searchParams] = useSearchParams();
  const token = useMemo(() => searchParams.get('token')?.trim() ?? '', [searchParams]);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [status, setStatus] = useState<SubmitStatus>('idle');
  const [message, setMessage] = useState<string | undefined>();

  const tokenMissing = !token;
  const passwordMismatch = Boolean(passwordConfirm) && password !== passwordConfirm;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(undefined);

    if (tokenMissing) {
      setStatus('error');
      setMessage('Your invite link is missing or incomplete. Please request a new invite.');
      return;
    }

    if (passwordMismatch) {
      setStatus('error');
      setMessage('Passwords do not match.');
      return;
    }

    setStatus('submitting');
    try {
      const payload: Record<string, string> = {
        token,
        password,
      };
      const normalizedFirstName = firstName.trim();
      const normalizedLastName = lastName.trim();
      if (normalizedFirstName) {
        payload.first_name = normalizedFirstName;
      }
      if (normalizedLastName) {
        payload.last_name = normalizedLastName;
      }

      await apiClient.post('/users/accept-invite/', payload, { skipAuth: true });
      setStatus('success');
      setMessage('Account created. You can sign in now.');
    } catch (error) {
      const resolved = error instanceof Error ? error.message : 'Unable to accept the invitation.';
      setStatus('error');
      setMessage(resolved);
    }
  };

  return (
    <div className="auth-shell">
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <h1>Accept invite</h1>
        <p className="muted">Set your name and password to activate access.</p>
        <label htmlFor="firstName">First name</label>
        <input
          id="firstName"
          type="text"
          value={firstName}
          onChange={(event) => setFirstName(event.target.value)}
          autoComplete="given-name"
        />
        <label htmlFor="lastName">Last name</label>
        <input
          id="lastName"
          type="text"
          value={lastName}
          onChange={(event) => setLastName(event.target.value)}
          autoComplete="family-name"
        />
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          minLength={8}
          required
          autoComplete="new-password"
        />
        <label htmlFor="passwordConfirm">Confirm password</label>
        <input
          id="passwordConfirm"
          type="password"
          value={passwordConfirm}
          onChange={(event) => setPasswordConfirm(event.target.value)}
          minLength={8}
          required
          autoComplete="new-password"
        />
        {message ? (
          <p className={`status-message ${status === 'error' ? 'error' : 'muted'}`}>{message}</p>
        ) : null}
        <button
          type="submit"
          disabled={status === 'submitting' || tokenMissing || passwordMismatch}
          className="button primary"
        >
          {status === 'submitting' ? 'Activating...' : 'Activate account'}
        </button>
        <div className="auth-links">
          <Link to="/login">Return to sign in</Link>
        </div>
      </form>
    </div>
  );
};

export default InviteAcceptPage;
