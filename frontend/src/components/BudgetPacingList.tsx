import useDashboardStore, { BudgetPacingRow } from '../state/useDashboardStore';
import { formatCurrency, formatPercent } from '../lib/format';

interface BudgetPacingListProps {
  rows: BudgetPacingRow[];
  currency: string;
}

const BudgetPacingList = ({ rows, currency }: BudgetPacingListProps) => {
  const { selectedParish } = useDashboardStore((state) => ({
    selectedParish: state.selectedParish,
  }));

  return (
    <div className="budget-list">
      {rows.length === 0 ? (
        <p className="status-message muted">
          {selectedParish
            ? `No campaigns have pacing data for ${selectedParish} yet.`
            : 'No campaigns have pacing data for the selected parish yet.'}
        </p>
      ) : null}
      {rows.map((row) => {
        const pacingPercent = Math.max(0, Math.min(200, row.pacingPercent * 100));
        const status = pacingPercent < 95 ? 'under' : pacingPercent > 110 ? 'over' : 'on-track';
        return (
          <article key={row.id} className={`budget-item budget-item--${status}`}>
            <header>
              <h4>{row.campaignName}</h4>
              <span className="budget-range">
                {row.startDate ? new Date(row.startDate).toLocaleDateString() : ''}
                {row.startDate && row.endDate ? ' – ' : ''}
                {row.endDate ? new Date(row.endDate).toLocaleDateString() : ''}
              </span>
            </header>
            <p className="status-message muted">
              Monthly budget {formatCurrency(row.monthlyBudget, currency)} · spend to date{' '}
              <strong>{formatCurrency(row.spendToDate, currency)}</strong>
            </p>
            <div className="progress-track" aria-hidden="true">
              <div className="progress-bar" style={{ width: `${pacingPercent}%` }} />
            </div>
            <footer>
              <span>{formatPercent(row.pacingPercent, 0)} pace</span>
              <span>Projected {formatCurrency(row.projectedSpend, currency)}</span>
            </footer>
          </article>
        );
      })}
    </div>
  );
};

export default BudgetPacingList;
