import { useEffect, useMemo } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

import Button from '../components/ui/Button'
import StatusMessage from '../components/ui/StatusMessage'
import { useAuth } from '../features/auth/AuthContext'
import useDashboardStore from '../features/dashboard/store/useDashboardStore'

import styles from './DashboardLayout.module.css'

const metricOptions = [
  { value: 'spend', label: 'Spend' },
  { value: 'impressions', label: 'Impressions' },
  { value: 'clicks', label: 'Clicks' },
  { value: 'conversions', label: 'Conversions' },
  { value: 'roas', label: 'ROAS' },
]

const DashboardLayout = () => {
  const { tenantId, logout, user } = useAuth()
  const {
    loadAll,
    selectedMetric,
    setSelectedMetric,
    selectedParish,
    campaign,
    creative,
    budget,
    parish,
  } = useDashboardStore((state) => ({
    loadAll: state.loadAll,
    selectedMetric: state.selectedMetric,
    setSelectedMetric: state.setSelectedMetric,
    selectedParish: state.selectedParish,
    campaign: state.campaign,
    creative: state.creative,
    budget: state.budget,
    parish: state.parish,
  }))

  useEffect(() => {
    void loadAll(tenantId)
  }, [loadAll, tenantId])

  const errors = useMemo(() => {
    return [campaign, creative, budget, parish]
      .filter((slice) => slice.status === 'error' && slice.error)
      .map((slice) => slice.error as string)
  }, [budget, campaign, creative, parish])

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div>
          <h1>ADinsights</h1>
          <p className={styles.headerMuted}>
            Tenant <strong>{tenantId ?? 'unknown'}</strong>
            {selectedParish ? (
              <span>
                {' • '}Filtering to <strong>{selectedParish}</strong>
              </span>
            ) : null}
          </p>
        </div>
        <div className={styles.headerActions}>
          <label htmlFor="metric-select" className={styles.headerMuted}>
            Map metric
          </label>
          <select
            id="metric-select"
            value={selectedMetric}
            onChange={(event) => setSelectedMetric(event.target.value as typeof selectedMetric)}
            className={styles.select}
          >
            {metricOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <span className={styles.userPill}>
            {(user as { email?: string } | undefined)?.email ?? 'Account'}
          </span>
          <Button variant="tertiary" onClick={logout}>
            Log out
          </Button>
        </div>
      </header>
      <nav className={styles.nav}>
        <NavLink
          to="/dashboards/campaigns"
          className={({ isActive }) =>
            isActive ? `${styles.navLink} ${styles.navLinkActive}` : styles.navLink
          }
        >
          Campaigns
        </NavLink>
        <NavLink
          to="/dashboards/creatives"
          className={({ isActive }) =>
            isActive ? `${styles.navLink} ${styles.navLinkActive}` : styles.navLink
          }
        >
          Creatives
        </NavLink>
        <NavLink
          to="/dashboards/budget"
          className={({ isActive }) =>
            isActive ? `${styles.navLink} ${styles.navLinkActive}` : styles.navLink
          }
        >
          Budget pacing
        </NavLink>
      </nav>
      {errors.length > 0 ? (
        <StatusMessage variant="error" role="alert">
          {errors.map((message, index) => (
            <span key={`${message}-${index}`}>{message}</span>
          ))}
        </StatusMessage>
      ) : null}
      <main className={styles.content}>
        <Outlet />
      </main>
    </div>
  )
}

export default DashboardLayout
