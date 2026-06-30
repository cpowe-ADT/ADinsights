import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { ColumnDef } from '@tanstack/react-table';

import {
  AccessibleTableToggle,
  BubbleScatter,
  ChartSkeleton,
  EmptyState,
  KpiTile,
  TrendLine,
  VizDataTable,
  type KpiTileProps,
} from '../components/viz';
import type { BubbleScatterDatum } from '../components/viz/BubbleScatter';
import type { TrendLinePoint } from '../components/viz/TrendLine';
import { useToastStore } from '../stores/useToastStore';
import { syncMetaIntegration } from '../lib/airbyte';
import { ApiError } from '../lib/apiClient';
import { formatCurrency, formatNumber, formatPercent } from '../lib/format';
import type { MetaInsightRecord } from '../lib/meta';
import {
  aggregatedRoas,
  derivedRoas,
  groupCtrCpmByDate,
  hasPurchaseActions,
  sumInsights,
} from '../lib/metaAggregates';
import useMetaStore from '../state/useMetaStore';

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

type InsightsTableRow = {
  id: string;
  campaign: string;
  spend: number;
  impressions: number;
  ctr: number;
  cpm: number;
  roas: number | null;
  objective: string;
};

type InsightsColumn = ColumnDef<InsightsTableRow, unknown>;

const MetaInsightsDashboardPage = () => {
  const [syncing, setSyncing] = useState(false);
  const addToast = useToastStore((s) => s.addToast);
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

  const rows: MetaInsightRecord[] = insights.rows;

  // Dual-axis CTR + CPM trend
  const trendPoints = useMemo(() => groupCtrCpmByDate(rows), [rows]);

  // Headline KPIs (includes ROAS conditional)
  const kpis = useMemo(() => sumInsights(rows), [rows]);
  const roas = useMemo(() => aggregatedRoas(rows), [rows]);
  const roasAvailable = useMemo(() => hasPurchaseActions(rows), [rows]);

  const kpiTiles: KpiTileProps[] = useMemo(() => {
    const tiles: KpiTileProps[] = [
      {
        label: 'Spend',
        value: rows.length ? kpis.spend : null,
        format: 'currency',
        currency: 'USD',
      },
    ];
    if (roasAvailable) {
      tiles.push({ label: 'ROAS', value: roas, format: 'number', hint: 'Revenue / spend' });
    }
    tiles.push(
      { label: 'CTR', value: rows.length ? kpis.ctr : null, format: 'percent' },
      // Frequency is not derivable from MetaInsightRecord; substitute CPC per §3 audit.
      { label: 'CPC', value: rows.length ? kpis.cpc : null, format: 'currency', currency: 'USD' },
      { label: 'CPM', value: rows.length ? kpis.cpm : null, format: 'currency', currency: 'USD' },
    );
    return tiles;
  }, [rows.length, kpis.spend, kpis.ctr, kpis.cpc, kpis.cpm, roas, roasAvailable]);

  // BubbleScatter data. Prefer campaign-level insights; fall back to whatever
  // level the user selected if no campaign rows are present (e.g. when
  // `filters.level !== 'campaign'` the slice may only carry account-level rows).
  const campaignRows = useMemo(() => {
    const campaign = rows.filter((r) => r.level === 'campaign');
    return campaign.length > 0 ? campaign : rows;
  }, [rows]);

  const bubbleData = useMemo<BubbleScatterDatum[]>(() => {
    return campaignRows.map((row) => {
      const roasForRow = derivedRoas(row);
      const cpmForRow = Number(row.cpm) || 0;
      const yValue = roasAvailable ? (roasForRow ?? 0) : cpmForRow;
      const shape: BubbleScatterDatum['shape'] = filters.accountId ? 'triangle' : 'circle';
      return {
        id: row.id,
        label: row.external_id,
        x: Number(row.spend) || 0,
        y: yValue,
        z: Number(row.impressions) || 0,
        shape,
      };
    });
  }, [campaignRows, filters.accountId, roasAvailable]);

  // Table rows (replacing the old @tanstack/react-table grid)
  const tableRows: InsightsTableRow[] = useMemo(
    () =>
      campaignRows.map((row) => {
        const spend = Number(row.spend) || 0;
        const impressions = Number(row.impressions) || 0;
        const clicks = Number(row.clicks) || 0;
        return {
          id: row.id,
          campaign: row.external_id,
          spend,
          impressions,
          ctr: impressions > 0 ? clicks / impressions : 0,
          cpm: impressions > 0 ? (spend / impressions) * 1000 : 0,
          roas: derivedRoas(row),
          objective: row.level,
        };
      }),
    [campaignRows],
  );

  const tableColumns = useMemo<InsightsColumn[]>(
    () => [
      { accessorKey: 'campaign', header: 'Campaign' },
      {
        accessorKey: 'spend',
        header: 'Spend',
        cell: (info) => formatCurrency(Number(info.getValue()), 'USD', 2),
      },
      {
        accessorKey: 'impressions',
        header: 'Impressions',
        cell: (info) => formatNumber(Number(info.getValue())),
      },
      {
        accessorKey: 'ctr',
        header: 'CTR',
        cell: (info) => formatPercent(Number(info.getValue())),
      },
      {
        accessorKey: 'cpm',
        header: 'CPM',
        cell: (info) => formatCurrency(Number(info.getValue()), 'USD', 2),
      },
      {
        accessorKey: 'roas',
        header: 'ROAS',
        cell: (info) => {
          const value = info.getValue();
          return value === null ? '—' : formatNumber(Number(value));
        },
      },
      { accessorKey: 'objective', header: 'Level' },
    ],
    [],
  );

  const handleSyncNow = async () => {
    if (syncing) {
      return;
    }
    setSyncing(true);
    try {
      const payload = await syncMetaIntegration();
      if (payload.reused_existing_job) {
        addToast(
          payload.job_id
            ? `Meta sync is already running (job ${payload.job_id}).`
            : 'Meta sync is already running.',
          'success',
        );
      } else {
        addToast(
          payload.job_id ? `Meta sync queued (job ${payload.job_id}).` : 'Meta sync triggered.',
          'success',
        );
      }
      await Promise.all([loadAccounts(), loadInsights()]);
    } catch (error) {
      const message =
        error instanceof ApiError || error instanceof Error
          ? error.message
          : 'Unable to trigger Meta sync.';
      addToast(message, 'error');
    } finally {
      setSyncing(false);
    }
  };

  const insightsLoading = insights.status === 'loading' && rows.length === 0;

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
          <button
            type="button"
            className="button secondary"
            onClick={() => void handleSyncNow()}
            disabled={syncing}
          >
            {syncing ? 'Syncing…' : 'Sync now'}
          </button>
        </div>
      </div>

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
          reasonCode="error"
        />
      ) : null}

      {insights.status !== 'error' && insights.status !== 'loading' && rows.length === 0 ? (
        <EmptyState
          icon={<span aria-hidden>0</span>}
          title="No insights in selected range"
          message="Run an insights sync for this account and date range."
          actionLabel={syncing ? 'Syncing…' : 'Sync now'}
          onAction={() => void handleSyncNow()}
          className="panel"
          reasonCode="no_data_for_range"
        />
      ) : null}

      {/* KPI strip */}
      <article className="panel" style={{ marginBottom: '1rem' }} data-testid="meta-insights-kpis">
        {insightsLoading ? (
          <ChartSkeleton variant="kpi-strip" />
        ) : (
          <div
            className="viz-kpi-strip"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
              gap: '0.75rem',
            }}
          >
            {kpiTiles.map((tile) => (
              <KpiTile key={tile.label} {...tile} />
            ))}
          </div>
        )}
      </article>

      {rows.length > 0 ? (
        <>
          {/* Dual-axis trend: CTR (left) + CPM (right) */}
          <article className="panel" style={{ marginBottom: '1rem' }}>
            <h3>CTR and CPM trend</h3>
            <AccessibleTableToggle
              chartAriaLabel="CTR and CPM per day"
              chart={
                <TrendLine
                  data={trendPoints as unknown as TrendLinePoint[]}
                  series={[
                    { key: 'ctr', label: 'CTR', yAxis: 'left' },
                    { key: 'cpm', label: 'CPM', yAxis: 'right' },
                  ]}
                  yFormat="percent"
                  rightYFormat="currency"
                  currency="USD"
                  ariaLabel="CTR and CPM per day"
                />
              }
              table={
                <VizDataTable
                  columns={[
                    { accessorKey: 'campaign', header: 'Date' } as InsightsColumn,
                    {
                      accessorKey: 'ctr',
                      header: 'CTR',
                      cell: (info) => formatPercent(Number(info.getValue())),
                    } as InsightsColumn,
                    {
                      accessorKey: 'cpm',
                      header: 'CPM',
                      cell: (info) => formatCurrency(Number(info.getValue()), 'USD', 2),
                    } as InsightsColumn,
                  ]}
                  data={trendPoints.map((p) => ({
                    id: p.date,
                    campaign: p.date,
                    spend: 0,
                    impressions: 0,
                    ctr: p.ctr,
                    cpm: p.cpm,
                    roas: null,
                    objective: '',
                  }))}
                  caption="CTR and CPM per day (tabular)"
                  captionHidden
                />
              }
            />
          </article>

          {/* Bubble scatter */}
          <article className="panel" style={{ marginBottom: '1rem' }}>
            <h3>
              {roasAvailable ? 'Spend vs. ROAS' : 'Spend vs. CPM'}{' '}
              <span className="status-message muted" style={{ fontSize: '0.85rem' }}>
                (bubble size = impressions)
              </span>
            </h3>
            <AccessibleTableToggle
              chartAriaLabel={
                roasAvailable
                  ? 'Spend versus ROAS by campaign, bubble size shows impressions'
                  : 'Spend versus CPM by campaign, bubble size shows impressions'
              }
              chart={
                <BubbleScatter
                  data={bubbleData}
                  xLabel="Spend"
                  yLabel={roasAvailable ? 'ROAS' : 'CPM'}
                  zLabel="Impressions"
                  xFormat="currency"
                  yFormat={roasAvailable ? 'number' : 'currency'}
                  zFormat="number"
                  currency="USD"
                  ariaLabel={
                    roasAvailable ? 'Spend versus ROAS by campaign' : 'Spend versus CPM by campaign'
                  }
                />
              }
              table={
                <VizDataTable
                  columns={[
                    { accessorKey: 'campaign', header: 'Campaign' } as InsightsColumn,
                    {
                      accessorKey: 'spend',
                      header: 'Spend',
                      cell: (info) => formatCurrency(Number(info.getValue()), 'USD', 2),
                    } as InsightsColumn,
                    {
                      accessorKey: 'impressions',
                      header: 'Impressions',
                      cell: (info) => formatNumber(Number(info.getValue())),
                    } as InsightsColumn,
                    {
                      accessorKey: 'cpm',
                      header: roasAvailable ? 'ROAS' : 'CPM',
                      cell: (info) => {
                        const value = Number(info.getValue());
                        return roasAvailable
                          ? formatNumber(value)
                          : formatCurrency(value, 'USD', 2);
                      },
                    } as InsightsColumn,
                  ]}
                  data={tableRows}
                  caption={
                    roasAvailable
                      ? 'Spend vs ROAS by campaign (tabular)'
                      : 'Spend vs CPM by campaign (tabular)'
                  }
                  captionHidden
                />
              }
            />
          </article>

          {/* Data table */}
          <article className="panel">
            <h3>Insights records ({insights.count})</h3>
            <VizDataTable columns={tableColumns} data={tableRows} ariaLabel="Top campaigns table" />
          </article>
        </>
      ) : null}
    </section>
  );
};

export default MetaInsightsDashboardPage;
