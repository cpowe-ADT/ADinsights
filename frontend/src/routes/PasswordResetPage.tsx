import { FormEvent, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import apiClient from '../lib/apiClient';

type SubmitStatus = 'idle' | 'submitting' | 'success' | 'error';

const PasswordResetPage = () => {
  const [searchParams] = useSearchParams();
  const token = useMemo(() => searchParams.get('token')?.trim() ?? '', [searchParams]);
  const isConfirmMode = Boolean(token);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [status, setStatus] = useState<SubmitStatus>('idle');
  const [message, setMessage] = useState<string | undefined>();

  const passwordMismatch = Boolean(passwordConfirm) && password !== passwordConfirm;

  const handleRequest = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatus('submitting');
    setMessage(undefined);

    try {
      await apiClient.post('/auth/password-reset/', { email }, { skipAuth: true });
      setStatus('success');
      setMessage('Check your inbox for a reset link.');
    } catch (error) {
      const resolved = error instanceof Error ? error.message : 'Unable to request a reset link.';
      setStatus('error');
      setMessage(resolved);
    }
  };

  const handleConfirm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(undefined);

    if (passwordMismatch) {
      setStatus('error');
      setMessage('Passwords do not match.');
      return;
    }

    setStatus('submitting');
    try {
      await apiClient.post(
        '/auth/password-reset/confirm/',
        { token, password },
        { skipAuth: true },
      );
      setStatus('success');
      setMessage('Password updated. You can sign in now.');
    } catch (error) {
      const resolved = error instanceof Error ? error.message : 'Unable to reset your password.';
      setStatus('error');
      setMessage(resolved);
    }
  };

  return (
    <div className="auth-shell">
      <form
        className="auth-form"
        onSubmit={isConfirmMode ? handleConfirm : handleRequest}
        noValidate
      >
        <h1>{isConfirmMode ? 'Set a new password' : 'Reset your password'}</h1>
        <p className="muted">
          {isConfirmMode
            ? 'Create a fresh password for your account.'
            : 'Enter your email and we will send a reset link.'}
        </p>
        {isConfirmMode ? (
          <>
            <label htmlFor="password">New password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={8}
              required
              autoComplete="new-password"
            />
            <label htmlFor="passwordConfirm">Confirm new password</label>
            <input
              id="passwordConfirm"
              type="password"
              value={passwordConfirm}
              onChange={(event) => setPasswordConfirm(event.target.value)}
              minLength={8}
              required
              autoComplete="new-password"
            />
          </>
        ) : (
          <>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              autoComplete="email"
            />
          </>
        )}
        {message ? (
          <p className={`status-message ${status === 'error' ? 'error' : 'muted'}`}>{message}</p>
        ) : null}
        <button
          type="submit"
          disabled={status === 'submitting' || (isConfirmMode && passwordMismatch)}
          className="button primary"
        >
          {status === 'submitting'
            ? 'Working...'
            : isConfirmMode
              ? 'Update password'
              : 'Send reset link'}
        </button>
        <div className="auth-links">
          <Link to="/login">Return to sign in</Link>
        </div>
      </form>
    </div>
  );
};

export default PasswordResetPage;
