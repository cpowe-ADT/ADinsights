import { FormEvent, useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import Button from '../components/ui/Button'
import StatusMessage from '../components/ui/StatusMessage'
import { useAuth } from '../features/auth/AuthContext'

import styles from './LoginPage.module.css'

const LoginPage = () => {
  const { login, status, error, isAuthenticated } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const navigate = useNavigate()
  const location = useLocation()

  const from =
    (location.state as { from?: { pathname?: string } } | undefined)?.from?.pathname ??
    '/dashboards/campaigns'

  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true })
    }
  }, [from, isAuthenticated, navigate])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch {
      // handled via auth state
    }
  }

  return (
    <div className={styles.shell}>
      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        <h1>ADinsights</h1>
        <p className={styles.subtitle}>Sign in to access client dashboards.</p>
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          autoComplete="email"
          className={styles.input}
        />
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          autoComplete="current-password"
          className={styles.input}
        />
        {error ? <StatusMessage variant="error">{error}</StatusMessage> : null}
        <Button type="submit" disabled={status === 'authenticating'}>
          {status === 'authenticating' ? 'Signing in…' : 'Sign In'}
        </Button>
      </form>
    </div>
  )
}

export default LoginPage
