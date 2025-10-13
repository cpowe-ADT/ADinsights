import BudgetPacingList from '../components/BudgetPacingList'
import FullPageLoader from '../components/FullPageLoader'
import DashboardShell, { DashboardPanel } from '../components/layout/DashboardShell'
import StatusMessage from '../components/ui/StatusMessage'
import useDashboardStore from '../features/dashboard/store/useDashboardStore'

import styles from './BudgetDashboard.module.css'

const BudgetDashboard = () => {
  const { budget, campaign, budgetRows } = useDashboardStore((state) => ({
    budget: state.budget,
    campaign: state.campaign,
    budgetRows: state.getBudgetRowsForSelectedParish(),
  }))

  const currency = campaign.data?.summary.currency ?? 'USD'

  if (budget.status === 'loading' && !budget.data) {
    return <FullPageLoader message="Loading budget pacing…" />
  }

  if (budget.status === 'error' && !budget.data) {
    return (
      <StatusMessage variant="error">
        {budget.error ?? 'Unable to load budget pacing.'}
      </StatusMessage>
    )
  }

  if (!budget.data) {
    return (
      <StatusMessage variant="muted">
        Budget pacing will appear once campaigns have budgets configured.
      </StatusMessage>
    )
  }

  return (
    <DashboardShell layout="single">
      <DashboardPanel fullWidth>
        <header className={styles.panelHeader}>
          <h2 className={styles.panelTitle}>Monthly pacing</h2>
          <p className={styles.panelDescription}>Compare current spend against planned budgets.</p>
        </header>
        <BudgetPacingList rows={budgetRows} currency={currency} />
      </DashboardPanel>
    </DashboardShell>
  )
}

export default BudgetDashboard
