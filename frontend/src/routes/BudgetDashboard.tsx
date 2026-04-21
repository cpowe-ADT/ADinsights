import { useCallback, useMemo } from 'react';

import BudgetPacingList from '../components/BudgetPacingList';
import DashboardState from '../components/DashboardState';
import FilterStatus from '../components/FilterStatus';
import {
  AccessibleTableToggle,
  DistributionBar,
  KpiTile,
  TrendLine,
  VizDataTable,
  derivePacingVariant,
} from '../components/viz';
import { PLATFORM_CHART_TOKENS } from '../styles/chartTheme';
import { useAuth } from '../auth/AuthContext';
import { messageForLiveDatasetReason, titleForLiveDatasetReason } from '../lib/datasetStatus';
import useDashboardStore from '../state/useDashboardStore';
import { useDatasetStore } from '../state/useDatasetStore';
import type { BudgetPacingRow } from '../state/useDashboardStore';

const BudgetEmptyIcon = () => (
  <svg
    width="48"
    height="48"
    viewBox="0 0 48 48"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.2"
  >
    <rect x="10" y="12" width="28" height="20" rx="3" />
    <path d="M16 20h16M16 26h10" strokeLinecap="round" />
    <path d="M28 30h8" strokeLinecap="round" />
  </svg>
);

type PlatformKey = keyof typeof PLATFORM_CHART_TOKENS;
const platformColor = (platform?: string): string | undefined => {
  if (!platform) return undefined;
  const key = platform.toLowerCase() as PlatformKey;
  return PLATFORM_CHART_TOKENS[key];
};

const BudgetDashboard = () => {
  const { tenantId } = useAuth();
  const { budget, campaign, budgetRows, availability } = useDashboardStore((state) => ({
    budget: state.budget,
    campaign: state.campaign,
    budgetRows: state.getBudgetRowsForSelectedParish(),
    availability: state.availability,
  }));
  const loadAll = useDashboardStore((state) => state.loadAll);
  const datasetMode = useDatasetStore((state) => state.mode);
  const datasetSource = useDatasetStore((state) => state.source);
  const liveReason = useDatasetStore((state) => state.liveReason);
  const liveDetail = useDatasetStore((state) => state.liveDetail);

  const currency = campaign.data?.summary.currency ?? 'USD';
  const budgetAvailability = availability?.budget;
  const liveDatasetBlocked =
    datasetMode === 'live' && datasetSource === 'warehouse' && liveReason && liveReason !== 'ready';
  const liveDatasetMessage = liveReason
    ? messageForLiveDatasetReason(liveReason, liveDetail)
    : null;
  // FP-BUDG-01: Guard against undefined availability (e.g. demo adapter) triggering false empty state.
  // Only show empty state when availability is explicitly populated and non-available,
  // OR when there is genuinely no budget data yet.
  const shouldShowEmptyState =
    (budgetAvailability !== undefined && budgetAvailability.status !== 'available') ||
    (!budget.data && budget.status !== 'loading');
  const handleRetry = useCallback(() => {
    void loadAll(tenantId, { force: true });
  }, [loadAll, tenantId]);

  // ---- Aggregates for the new viz-kit primitives ----
  const totals = useMemo(() => {
    const spendToDate = budgetRows.reduce((sum, row) => sum + (row.spendToDate ?? 0), 0);
    const totalBudget = budgetRows.reduce(
      (sum, row) => sum + (row.windowBudget ?? row.monthlyBudget),
      0,
    );
    const pacing = totalBudget > 0 ? spendToDate / totalBudget : 0;
    return { spendToDate, totalBudget, pacing };
  }, [budgetRows]);

  const distributionRows = useMemo(
    () =>
      budgetRows.map((row) => {
        const budget = row.windowBudget ?? row.monthlyBudget;
        return {
          id: row.id,
          label: row.campaignName,
          platform: row.platform,
          spend: row.spendToDate,
          budget,
          hasBudget: budget > 0,
          pacing: budget > 0 ? row.spendToDate / budget : 0,
          projectedSpend: row.projectedSpend,
        };
      }),
    [budgetRows],
  );

  // Cumulative spend trend vs total-budget ceiling (derived from campaign.data.trend).
  const trendData = useMemo(() => {
    const trend = campaign.data?.trend ?? [];
    let cumulative = 0;
    return trend.map((point) => {
      cumulative += Number(point.spend || 0);
      return { date: point.date, cumulativeSpend: cumulative };
    });
  }, [campaign.data]);

  const trendBudgetLine = useMemo(() => {
    if (trendData.length === 0 || totals.totalBudget <= 0) return undefined;
    return trendData.map((point) => ({ date: point.date, value: totals.totalBudget }));
  }, [trendData, totals.totalBudget]);

  const tableColumns = useMemo(
    () => [
      { accessorKey: 'label', header: 'Campaign' },
      {
        accessorKey: 'platform',
        header: 'Platform',
        cell: ({ row }: { row: { original: typeof distributionRows[number] } }) => {
          const color = platformColor(row.original.platform);
          if (!row.original.platform) return '—';
          return (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '2px 8px',
                borderRadius: 999,
                background: color ? `${color}22` : 'rgba(148,163,184,0.15)',
                color: color ?? 'inherit',
                fontSize: '0.75rem',
                fontWeight: 600,
              }}
            >
              <span
                aria-hidden
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: color ?? '#94a3b8',
                }}
              />
              {row.original.platform}
            </span>
          );
        },
      },
      {
        accessorKey: 'spend',
        header: 'Spend to date',
        cell: ({ row }: { row: { original: typeof distributionRows[number] } }) =>
          row.original.spend.toLocaleString(undefined, {
            style: 'currency',
            currency,
          }),
      },
      {
        accessorKey: 'budget',
        header: 'Budget',
        cell: ({ row }: { row: { original: typeof distributionRows[number] } }) =>
          row.original.hasBudget
            ? row.original.budget.toLocaleString(undefined, {
                style: 'currency',
                currency,
              })
            : 'Budget unavailable',
      },
      {
        accessorKey: 'pacing',
        header: 'Pacing',
        cell: ({ row }: { row: { original: typeof distributionRows[number] } }) => {
          if (!row.original.hasBudget) return '—';
          const variant = derivePacingVariant(row.original.pacing);
          const tone =
            variant === 'ok'
              ? { bg: 'rgba(34,197,94,0.15)', fg: '#166534' }
              : variant === 'warning'
                ? { bg: 'rgba(234,179,8,0.18)', fg: '#854d0e' }
                : { bg: 'rgba(239,68,68,0.18)', fg: '#991b1b' };
          return (
            <span
              data-testid="pacing-risk-chip"
              data-variant={variant}
              style={{
                padding: '2px 8px',
                borderRadius: 999,
                background: tone.bg,
                color: tone.fg,
                fontSize: '0.75rem',
                fontWeight: 600,
              }}
            >
              {`${Math.round(row.original.pacing * 100)}%`}
            </span>
          );
        },
      },
    ],
    [currency],
  );

  if (budget.status === 'loading' && !budget.data) {
    return <DashboardState variant="loading" layout="page" message="Loading budget pacing..." />;
  }

  if (budget.status === 'error' && !budget.data) {
    if (liveDatasetBlocked) {
      return (
        <div className="dashboard-grid single-panel">
          <section className="panel full-width">
            <DashboardState
              variant="empty"
              icon={<BudgetEmptyIcon />}
              title={titleForLiveDatasetReason(liveReason)}
              message={liveDatasetMessage ?? 'Live warehouse metrics are unavailable.'}
              actionLabel="Refresh data"
              onAction={handleRetry}
              layout="panel"
            />
          </section>
        </div>
      );
    }
    const errorTitle =
      budget.errorKind === 'stale_snapshot'
        ? 'Dashboard data is refreshing'
        : budget.errorKind === 'network'
          ? 'Unable to connect'
          : 'Budget pacing';
    return (
      <div className="dashboard-grid single-panel">
        <section className="panel full-width">
          <DashboardState
            variant="error"
            title={errorTitle}
            message={budget.error ?? 'Unable to load budget pacing.'}
            actionLabel="Retry load"
            onAction={handleRetry}
            layout="panel"
          />
        </section>
      </div>
    );
  }

  if (shouldShowEmptyState) {
    const emptyVariant = budgetAvailability?.reason === 'no_matching_filters' ? 'no-results' : 'empty';
    const emptyTitle =
      budgetAvailability?.reason === 'budget_unavailable'
        ? 'Budgets are unavailable for this view'
        : budgetAvailability?.reason === 'no_matching_filters'
          ? 'No budget rows match this view'
          : budgetAvailability?.reason === 'no_recent_data'
            ? 'No recent reportable data'
            : 'No budget pacing yet';
    const emptyMessage =
      budgetAvailability?.reason === 'budget_unavailable'
        ? 'Campaign performance exists, but no Meta ad set budgets were available for the selected client and range.'
        : budgetAvailability?.reason === 'no_matching_filters'
          ? 'No budget rows matched the selected client, range, or search filters.'
          : budgetAvailability?.reason === 'no_recent_data'
            ? 'The selected Meta account is connected, but Meta returned no recent reportable budget-backed delivery for this window.'
            : 'Budget pacing will appear once campaign budgets are configured.';
    return (
      <div className="dashboard-grid single-panel">
        <section className="panel full-width">
          <DashboardState
            variant={emptyVariant}
            icon={<BudgetEmptyIcon />}
            title={emptyTitle}
            message={emptyMessage}
            actionLabel="Refresh data"
            actionVariant="secondary"
            onAction={handleRetry}
            layout="panel"
          />
        </section>
      </div>
    );
  }

  return (
    <div className="dashboardGrid">
      {/* Block 1 — KPI strip (KpiTile × 3) */}
      <div className="kpiColumn" role="group" aria-label="Budget KPIs">
        <KpiTile
          label="Spend to date"
          value={totals.spendToDate}
          format="currency"
          currency={currency}
        />
        <KpiTile
          label="Total budget"
          value={totals.totalBudget > 0 ? totals.totalBudget : null}
          format="currency"
          currency={currency}
          hint={totals.totalBudget > 0 ? undefined : 'No budget available for this view'}
        />
        <KpiTile
          label="Overall pacing"
          value={totals.totalBudget > 0 ? totals.pacing : null}
          format="percent"
          reasonCode={totals.totalBudget > 0 ? undefined : 'budget_unavailable'}
        />
      </div>

      {/* Block 2 — Paired Spend vs Budget distribution */}
      <section className="panel full-width">
        <header className="panel-header">
          <div className="panel-header__title-row">
            <h2>Spend vs budget</h2>
            <FilterStatus />
          </div>
          <p className="muted">
            Per-campaign spend against window budget. Rows without a configured budget are tagged
            as <em>Budget unavailable</em>.
          </p>
        </header>
        <AccessibleTableToggle
          chartAriaLabel="Spend vs budget by campaign"
          chart={
            <DistributionBar
              ariaLabel="Spend to date per campaign (paired with budget)"
              data={distributionRows
                .filter((row) => row.hasBudget)
                .map((row) => ({
                  label: row.label,
                  value: row.spend,
                  color: platformColor(row.platform),
                }))}
              yFormat="currency"
              currency={currency}
              emptyReasonCode="no_matching_filters"
            />
          }
          table={
            <table className="dashboard-table">
              <thead>
                <tr>
                  <th>Campaign</th>
                  <th>Spend</th>
                  <th>Budget</th>
                </tr>
              </thead>
              <tbody>
                {distributionRows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.label}</td>
                    <td>{row.spend}</td>
                    <td>{row.hasBudget ? row.budget : 'Budget unavailable'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          }
        />
        {distributionRows.some((row) => !row.hasBudget) ? (
          <p className="muted" style={{ marginTop: '0.5rem' }}>
            Budget unavailable for:{' '}
            {distributionRows
              .filter((row) => !row.hasBudget)
              .map((row) => row.label)
              .join(', ')}
            .
          </p>
        ) : null}
      </section>

      {/* Block 3 — Cumulative spend vs total-budget ceiling trend */}
      {trendData.length > 0 ? (
        <section className="panel full-width">
          <header className="panel-header">
            <h2>Cumulative spend vs budget ceiling</h2>
            <p className="muted">
              Running spend total; the dashed ghost line marks the total-budget ceiling.
            </p>
          </header>
          <TrendLine
            ariaLabel="Cumulative spend over time with total budget ceiling"
            data={trendData}
            series={[
              {
                key: 'cumulativeSpend',
                label: 'Cumulative spend',
                color: PLATFORM_CHART_TOKENS.meta_ads,
              },
            ]}
            peerData={trendBudgetLine}
            yFormat="currency"
            currency={currency}
            emptyReasonCode="no_data_for_range"
          />
        </section>
      ) : null}

      {/* Block 4 — Drill-down VizDataTable */}
      {distributionRows.length > 0 ? (
        <section className="panel full-width">
          <VizDataTable
            ariaLabel="Budget pacing details"
            title="Budget pacing details"
            csvFilename="budget-pacing.csv"
            columns={tableColumns as never}
            data={distributionRows}
          />
        </section>
      ) : null}

      {/* Block 5 — Legacy pacing list retained for backward compatibility */}
      <section className="panel full-width">
        <header className="panel-header">
          <div className="panel-header__title-row">
            <h2>Budget pacing</h2>
          </div>
          <p className="muted">Compare projected spend against the selected-window Meta budget plan.</p>
        </header>
        <BudgetPacingList rows={budgetRows as BudgetPacingRow[]} currency={currency} />
      </section>

      {/* Platform-color legend — shown when any row has a platform */}
      {distributionRows.some((row) => row.platform) ? (
        <aside
          className="panel"
          aria-label="Platform color legend"
          style={{ display: 'flex', gap: '1rem', padding: '0.5rem 1rem' }}
        >
          {Array.from(
            new Set(
              distributionRows.map((row) => row.platform).filter((p): p is string => Boolean(p)),
            ),
          ).map((platform) => (
            <span
              key={platform}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.8rem' }}
            >
              <span
                aria-hidden
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: 3,
                  background: platformColor(platform) ?? '#94a3b8',
                }}
              />
              {platform}
            </span>
          ))}
        </aside>
      ) : null}
    </div>
  );
};

export default BudgetDashboard;
