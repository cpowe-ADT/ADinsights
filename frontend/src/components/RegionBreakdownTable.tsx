import { useMemo, useState } from 'react';

import { formatCurrency, formatNumber, formatPercent, formatRatio } from '../lib/format';
import useDashboardStore from '../state/useDashboardStore';
import DashboardState from './DashboardState';
import FilterStatus from './FilterStatus';
import Skeleton from './Skeleton';

type SortKey =
  | 'parish'
  | 'spend'
  | 'impressions'
  | 'clicks'
  | 'conversions'
  | 'ctr'
  | 'roas'
  | 'campaignCount';

type RegionBreakdownTableProps = {
  onReload?: () => void;
};

const classNames = (...values: Array<string | false | null | undefined>) =>
  values.filter(Boolean).join(' ');

const RegionBreakdownTable = ({ onReload }: RegionBreakdownTableProps) => {
  const { rows, status, selectedParish, setSelectedParish, currency } = useDashboardStore(
    (state) => ({
      rows: state.parish.data ?? [],
      status: state.parish.status,
      selectedParish: state.selectedParish,
      setSelectedParish: state.setSelectedParish,
      currency: state.campaign.data?.summary.currency ?? 'USD',
    }),
  );
  const [sorting, setSorting] = useState<{ key: SortKey; desc: boolean }>({
    key: 'spend',
    desc: true,
  });

  const sortedRows = useMemo(() => {
    const next = [...rows];
    next.sort((left, right) => {
      const direction = sorting.desc ? -1 : 1;
      if (sorting.key === 'parish') {
        return left.parish.localeCompare(right.parish) * direction;
      }
      const leftValue = Number(left[sorting.key] ?? 0);
      const rightValue = Number(right[sorting.key] ?? 0);
      if (leftValue === rightValue) {
        return left.parish.localeCompare(right.parish) * direction;
      }
      return (leftValue - rightValue) * direction;
    });
    return next;
  }, [rows, sorting]);

  const toggleSorting = (key: SortKey) => {
    setSorting((current) =>
      current.key === key ? { key, desc: !current.desc } : { key, desc: key !== 'parish' },
    );
  };

  if (status === 'loading' && rows.length === 0) {
    return (
      <div className="widget-skeleton" aria-busy="true">
        <Skeleton height={180} borderRadius="0.9rem" />
        <Skeleton width="40%" height="0.85rem" />
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <DashboardState
        variant="empty"
        title="No parish data available."
        message="Regional performance will appear once parish-level campaign data is available."
        actionLabel={onReload ? 'Refresh data' : undefined}
        onAction={onReload}
        actionVariant="secondary"
        layout="compact"
      />
    );
  }

  return (
    <div className="table-card">
      <div className="table-card__header">
        <div>
          <div className="table-card__title-row">
            <h3>Parish metrics</h3>
            <FilterStatus />
          </div>
          <p className="status-message muted">
            {selectedParish
              ? `Filtering to ${selectedParish}. Click the selected row again to clear it.`
              : 'Sort by any column or click a parish row to filter the dashboard.'}
          </p>
        </div>
      </div>
      <div className="table-responsive dashboard-table__scroll">
        <table className="dashboard-table">
          <thead>
            <tr className="dashboard-table__header-row">
              {[
                ['parish', 'Parish'],
                ['spend', 'Spend'],
                ['impressions', 'Impressions'],
                ['clicks', 'Clicks'],
                ['conversions', 'Conversions'],
                ['ctr', 'CTR'],
                ['roas', 'ROAS'],
                ['campaignCount', 'Campaign count'],
              ].map(([key, label]) => (
                <th key={key} className="dashboard-table__header-cell" scope="col">
                  <button
                    type="button"
                    onClick={() => toggleSorting(key as SortKey)}
                    className="sort-button"
                    aria-label={`Sort by ${label}`}
                  >
                    {label}
                    {sorting.key === key ? (sorting.desc ? ' ↓' : ' ↑') : ''}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row, index) => {
              const isSelected = selectedParish === row.parish;
              return (
                <tr
                  key={row.parish}
                  className={classNames(
                    'dashboard-table__row',
                    index % 2 === 1 && 'dashboard-table__row--zebra',
                    isSelected && 'dashboard-table__row--selected',
                  )}
                >
                  <td className="dashboard-table__cell">
                    <button
                      type="button"
                      className="table-link button-reset"
                      onClick={() => setSelectedParish(row.parish)}
                    >
                      {row.parish}
                    </button>
                  </td>
                  <td className="dashboard-table__cell dashboard-table__cell--numeric">
                    {formatCurrency(row.spend, row.currency ?? currency)}
                  </td>
                  <td className="dashboard-table__cell dashboard-table__cell--numeric">
                    {formatNumber(row.impressions)}
                  </td>
                  <td className="dashboard-table__cell dashboard-table__cell--numeric">
                    {formatNumber(row.clicks)}
                  </td>
                  <td className="dashboard-table__cell dashboard-table__cell--numeric">
                    {formatNumber(row.conversions)}
                  </td>
                  <td className="dashboard-table__cell dashboard-table__cell--numeric">
                    {formatPercent(row.ctr ?? 0, 2)}
                  </td>
                  <td className="dashboard-table__cell dashboard-table__cell--numeric">
                    {formatRatio(row.roas ?? 0, 2)}
                  </td>
                  <td className="dashboard-table__cell dashboard-table__cell--numeric">
                    {formatNumber(row.campaignCount ?? 0)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default RegionBreakdownTable;
