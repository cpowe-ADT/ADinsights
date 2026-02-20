import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from '@tanstack/react-table';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ComponentType } from 'react';

import EmptyState from '../components/EmptyState';
import { formatCurrency, formatNumber } from '../lib/format';
import type { MetaInsightRecord } from '../lib/meta';
import useMetaStore from '../state/useMetaStore';

const columnHelper = createColumnHelper<MetaInsightRecord>();

const columns = [
  columnHelper.accessor('date', {
    header: 'Date',
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor('level', {
    header: 'Level',
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor('external_id', {
    header: 'Entity ID',
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor('impressions', {
    header: 'Impressions',
    cell: (info) => formatNumber(info.getValue()),
  }),
  columnHelper.accessor('reach', {
    header: 'Reach',
    cell: (info) => formatNumber(info.getValue()),
  }),
  columnHelper.accessor('clicks', {
    header: 'Clicks',
    cell: (info) => formatNumber(info.getValue()),
  }),
  columnHelper.accessor('spend', {
    header: 'Spend',
    cell: (info) => formatCurrency(Number(info.getValue()), 'USD', 2),
  }),
  columnHelper.accessor('cpc', {
    header: 'CPC',
    cell: (info) => formatCurrency(Number(info.getValue()), 'USD', 2),
  }),
  columnHelper.accessor('cpm', {
    header: 'CPM',
    cell: (info) => formatCurrency(Number(info.getValue()), 'USD', 2),
  }),
  columnHelper.accessor('conversions', {
    header: 'Conversions',
    cell: (info) => formatNumber(info.getValue()),
  }),
];

function resolveInsightsErrorMessage(errorCode?: string, fallback?: string): string {
  if (errorCode === 'token_expired') {
    return 'Meta token expired. Reconnect Meta from Data Sources and retry.';
  }
  if (errorCode === 'permission_error') {
    return 'Missing Meta permissions. Re-run OAuth with required scopes.';
  }
  if (errorCode === 'rate_limited') {
    return 'Meta API is rate-limiting requests. Retry in a moment.';
  }
  return fallback ?? 'Try again.';
}

const MetaInsightsDashboardPage = () => {
  const [sorting, setSorting] = useState<SortingState>([{ id: 'date', desc: true }]);
  const { filters, setFilters, accounts, insights, loadAccounts, loadInsights } = useMetaStore(
    (state) => ({
      filters: state.filters,
      setFilters: state.setFilters,
      accounts: state.accounts,
      insights: state.insights,
      loadAccounts: state.loadAccounts,
      loadInsights: state.loadInsights,
    }),
  );

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);

  useEffect(() => {
    void loadInsights();
  }, [
    filters.accountId,
    filters.level,
    filters.search,
    filters.status,
    filters.since,
    filters.until,
    loadInsights,
  ]);

  const chartData = useMemo(() => {
    const grouped = new Map<
      string,
      { date: string; spend: number; clicks: number; impressions: number }
    >();
    insights.rows.forEach((row) => {
      const key = row.date;
      const existing = grouped.get(key) ?? { date: key, spend: 0, clicks: 0, impressions: 0 };
      existing.spend += Number(row.spend);
      existing.clicks += Number(row.clicks);
      existing.impressions += Number(row.impressions);
      grouped.set(key, existing);
    });
    return [...grouped.values()].sort((a, b) => a.date.localeCompare(b.date));
  }, [insights.rows]);

  const table = useReactTable({
    data: insights.rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const GridComponent = CartesianGrid as unknown as ComponentType<Record<string, unknown>>;
  const XAxisComponent = XAxis as unknown as ComponentType<Record<string, unknown>>;
  const YAxisComponent = YAxis as unknown as ComponentType<Record<string, unknown>>;
  const TooltipComponent = Tooltip as unknown as ComponentType<Record<string, unknown>>;
  const LineComponent = Line as unknown as ComponentType<Record<string, unknown>>;

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Meta data</p>
        <h1 className="dashboardHeading">Insights dashboard</h1>
        <div className="dashboard-header__actions-row">
          <Link className="button tertiary" to="/dashboards/meta/accounts">
            Accounts
          </Link>
          <Link className="button tertiary" to="/dashboards/meta/campaigns">
            Campaigns
          </Link>
        </div>
      </header>

      <div className="panel" style={{ marginBottom: '1rem' }}>
        <div className="dashboard-header__controls">
          <label className="dashboard-field">
            <span className="dashboard-field__label">Account</span>
            <select
              value={filters.accountId}
              onChange={(event) => setFilters({ accountId: event.target.value })}
            >
              <option value="">All ad accounts</option>
              {accounts.rows.map((account) => (
                <option key={account.id} value={account.external_id}>
                  {account.name || account.external_id}
                </option>
              ))}
            </select>
          </label>
          <label className="dashboard-field">
            <span className="dashboard-field__label">Level</span>
            <select
              value={filters.level}
              onChange={(event) =>
                setFilters({
                  level: event.target.value as 'account' | 'campaign' | 'adset' | 'ad',
                })
              }
            >
              <option value="account">Account</option>
              <option value="campaign">Campaign</option>
              <option value="adset">Ad Set</option>
              <option value="ad">Ad</option>
            </select>
          </label>
          <label className="dashboard-field">
            <span className="dashboard-field__label">Since</span>
            <input
              type="date"
              value={filters.since}
              onChange={(event) => setFilters({ since: event.target.value })}
            />
          </label>
          <label className="dashboard-field">
            <span className="dashboard-field__label">Until</span>
            <input
              type="date"
              value={filters.until}
              onChange={(event) => setFilters({ until: event.target.value })}
            />
          </label>
          <label className="dashboard-field">
            <span className="dashboard-field__label">Search</span>
            <input
              value={filters.search}
              onChange={(event) => setFilters({ search: event.target.value })}
              placeholder="Campaign/ad/adset id or name"
            />
          </label>
          <button type="button" className="button secondary" onClick={() => void loadInsights()}>
            Refresh
          </button>
        </div>
      </div>

      {insights.status === 'loading' && insights.rows.length === 0 ? (
        <div className="dashboard-state dashboard-state--page">Loading insights...</div>
      ) : null}

      {insights.status === 'stale' ? (
        <div className="dashboard-state" role="status" style={{ marginBottom: '1rem' }}>
          Showing stale insights data.{' '}
          {resolveInsightsErrorMessage(insights.errorCode, insights.error)}
        </div>
      ) : null}

      {insights.status === 'error' ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="Unable to load insights"
          message={resolveInsightsErrorMessage(insights.errorCode, insights.error)}
          actionLabel="Retry"
          onAction={() => void loadInsights()}
          className="panel"
        />
      ) : null}

      {insights.status !== 'error' && insights.rows.length === 0 ? (
        <EmptyState
          icon={<span aria-hidden>0</span>}
          title="No insights in selected range"
          message="Run an insights sync for this account and date range."
          className="panel"
        />
      ) : null}

      {insights.rows.length > 0 ? (
        <>
          <article className="panel" style={{ minHeight: 320, marginBottom: '1rem' }}>
            <h3>Spend trend</h3>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData}>
                <GridComponent strokeDasharray="3 3" />
                <XAxisComponent dataKey="date" />
                <YAxisComponent />
                <TooltipComponent />
                <LineComponent type="monotone" dataKey="spend" stroke="#2a8f72" strokeWidth={2} />
                <LineComponent type="monotone" dataKey="clicks" stroke="#1a4f8f" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </article>

          <article className="panel">
            <h3>Insights records ({insights.count})</h3>
            <div className="table-responsive">
              <table className="dashboard-table">
                <thead>
                  {table.getHeaderGroups().map((headerGroup) => (
                    <tr key={headerGroup.id} className="dashboard-table__header-row">
                      {headerGroup.headers.map((header) => (
                        <th key={header.id} className="dashboard-table__header-cell">
                          {header.isPlaceholder ? null : (
                            <button
                              type="button"
                              className="button tertiary"
                              onClick={header.column.getToggleSortingHandler()}
                            >
                              {flexRender(header.column.columnDef.header, header.getContext())}
                            </button>
                          )}
                        </th>
                      ))}
                    </tr>
                  ))}
                </thead>
                <tbody>
                  {table.getRowModel().rows.map((row) => (
                    <tr key={row.id} className="dashboard-table__row dashboard-table__row--zebra">
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="dashboard-table__cell">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </>
      ) : null}
    </section>
  );
};

export default MetaInsightsDashboardPage;
