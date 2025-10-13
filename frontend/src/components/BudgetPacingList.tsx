import useDashboardStore, { BudgetPacingRow } from '../features/dashboard/store/useDashboardStore'
import { formatCurrency, formatPercent } from '../lib/format'
import StatusMessage from './ui/StatusMessage'

import styles from './BudgetPacingList.module.css'

interface BudgetPacingListProps {
  rows: BudgetPacingRow[]
  currency: string
}

const BudgetPacingList = ({ rows, currency }: BudgetPacingListProps) => {
  const { selectedParish } = useDashboardStore((state) => ({
    selectedParish: state.selectedParish,
  }))

  return (
    <div className={styles.list}>
      {rows.length === 0 ? (
        <StatusMessage variant="muted">
          {selectedParish
            ? `No campaigns have pacing data for ${selectedParish} yet.`
            : 'No campaigns have pacing data for the selected parish yet.'}
        </StatusMessage>
      ) : null}
      {rows.map((row) => {
        const pacingPercent = Math.max(0, Math.min(200, row.pacingPercent * 100))
        const status = pacingPercent < 95 ? 'under' : pacingPercent > 110 ? 'over' : 'on-track'
        return (
          <article
            key={row.id}
            className={
              status === 'over'
                ? `${styles.item} ${styles.itemOver}`
                : status === 'under'
                  ? `${styles.item} ${styles.itemUnder}`
                  : styles.item
            }
          >
            <header>
              <h4>{row.campaignName}</h4>
              <span className={styles.range}>
                {row.startDate ? new Date(row.startDate).toLocaleDateString() : ''}
                {row.startDate && row.endDate ? ' – ' : ''}
                {row.endDate ? new Date(row.endDate).toLocaleDateString() : ''}
              </span>
            </header>
            <StatusMessage variant="muted">
              Monthly budget {formatCurrency(row.monthlyBudget, currency)} · spend to date{' '}
              <strong>{formatCurrency(row.spendToDate, currency)}</strong>
            </StatusMessage>
            <div className={styles.track} aria-hidden="true">
              <div className={styles.bar} style={{ width: `${pacingPercent}%` }} />
            </div>
            <footer className={styles.footer}>
              <span>{formatPercent(row.pacingPercent, 0)} pace</span>
              <span>Projected {formatCurrency(row.projectedSpend, currency)}</span>
            </footer>
          </article>
        )
      })}
    </div>
  )
}

export default BudgetPacingList
