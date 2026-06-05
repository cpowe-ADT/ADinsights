import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import type { ColumnDef } from '@tanstack/react-table';

import {
  AccessibleTableToggle,
  ChartSkeleton,
  EmptyState,
  KpiTile,
  PieComposition,
  TrendLine,
  VizDataTable,
  type KpiTileProps,
} from '../components/viz';
import type { TrendLineSeries } from '../components/viz/TrendLine';
import {
  loadSocialConnectionStatus,
  previewMetaRecovery,
  type MetaAdAccount,
  type SocialPlatformStatusRecord,
} from '../lib/airbyte';
import type { MetaAccount } from '../lib/meta';
import {
  computePeerMedian,
  groupSpendByDateAccount,
  spendByObjective,
  sumInsights,
  topAccountsBySpend,
} from '../lib/metaAggregates';
import useMetaStore from '../state/useMetaStore';

type AccountRow = MetaAccount & Record<string, unknown>;

function resolveAccountsErrorMessage(errorCode?: string, fallback?: string): string {
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

const TREND_TOP_N = 6;

type DisplayAccountRow = {
  id: string;
  name: string;
  external_id: string;
  account_id: string;
  currency: string;
  status: string;
  business_name: string;
};

type AccountsColumn = ColumnDef<DisplayAccountRow, unknown>;

const accountTableColumns: AccountsColumn[] = [
  { accessorKey: 'name', header: 'Name' },
  { accessorKey: 'external_id', header: 'External ID' },
  { accessorKey: 'account_id', header: 'Account ID' },
  { accessorKey: 'currency', header: 'Currency' },
  { accessorKey: 'status', header: 'Status' },
  { accessorKey: 'business_name', header: 'Business' },
];

const MetaAccountsPage = () => {
  const navigate = useNavigate();
  const {
    accounts,
    filters,
    setFilters,
    loadAccounts,
    loadCampaigns,
    loadInsights,
    campaigns,
    insights,
  } = useMetaStore((state) => ({
    accounts: state.accounts,
    filters: state.filters,
    setFilters: state.setFilters,
    loadAccounts: state.loadAccounts,
    loadCampaigns: state.loadCampaigns,
    loadInsights: state.loadInsights,
    campaigns: state.campaigns,
    insights: state.insights,
  }));

  const [metaStatus, setMetaStatus] = useState<SocialPlatformStatusRecord | null>(null);
  const [recoveryAccounts, setRecoveryAccounts] = useState<MetaAdAccount[]>([]);
  const [recoveryStatus, setRecoveryStatus] = useState<'idle' | 'loading' | 'loaded' | 'error'>(
    'idle',
  );
  const [recoveryError, setRecoveryError] = useState<string | null>(null);

  // Dispatch accounts / campaigns / account-level insights on mount + filter
  // changes. Per S2 §4.1: a single effect owns all three fetches so debounced
  // filter edits do not race a parallel effect.
  useEffect(() => {
    void loadAccounts();
    if (typeof loadCampaigns === 'function') {
      void loadCampaigns();
    }
    if (typeof loadInsights === 'function') {
      void loadInsights();
    }
  }, [
    filters.search,
    filters.status,
    filters.since,
    filters.until,
    loadAccounts,
    loadCampaigns,
    loadInsights,
  ]);

  useEffect(() => {
    let cancelled = false;

    const loadMetaStatus = async () => {
      try {
        const payload = await loadSocialConnectionStatus();
        if (cancelled) {
          return;
        }
        setMetaStatus(payload.platforms.find((row) => row.platform === 'meta') ?? null);
      } catch {
        if (!cancelled) {
          setMetaStatus(null);
        }
      }
    };

    void loadMetaStatus();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const shouldAttemptRecoveryPreview =
      accounts.status === 'loaded' &&
      accounts.rows.length === 0 &&
      metaStatus?.reason.code === 'orphaned_marketing_access';
    if (!shouldAttemptRecoveryPreview) {
      setRecoveryAccounts([]);
      setRecoveryStatus('idle');
      setRecoveryError(null);
      return;
    }

    const loadRecoveryPreview = async () => {
      setRecoveryStatus('loading');
      setRecoveryError(null);
      try {
        const payload = await previewMetaRecovery();
        if (cancelled) {
          return;
        }
        setRecoveryAccounts(payload.ad_accounts);
        setRecoveryStatus('loaded');
      } catch (error) {
        if (cancelled) {
          return;
        }
        setRecoveryAccounts([]);
        setRecoveryStatus('error');
        setRecoveryError(
          error instanceof Error
            ? error.message
            : 'Unable to preview recoverable Meta ad accounts.',
        );
      }
    };

    void loadRecoveryPreview();

    return () => {
      cancelled = true;
    };
  }, [accounts.rows.length, accounts.status, metaStatus?.reason.code]);

  const showRecoveryFallback =
    accounts.rows.length === 0 && recoveryStatus === 'loaded' && recoveryAccounts.length > 0;
  const displayedAccountCount = showRecoveryFallback ? recoveryAccounts.length : accounts.count;
  const orphanedMarketingAccess = metaStatus?.reason.code === 'orphaned_marketing_access';

  const visibleRows: DisplayAccountRow[] = useMemo(
    () =>
      showRecoveryFallback
        ? recoveryAccounts.map((account, index) => ({
            id: `${account.id}-${index}`,
            name: account.name || '—',
            external_id: account.id,
            account_id: account.account_id || '—',
            currency: account.currency || '—',
            status:
              account.account_status !== null && account.account_status !== undefined
                ? String(account.account_status)
                : '—',
            business_name: account.business_name || '—',
          }))
        : (accounts.rows as AccountRow[]).map((account) => ({
            id: String(account.id),
            name: String(account.name ?? '') || '—',
            external_id: String(account.external_id ?? ''),
            account_id: String(account.account_id ?? '') || '—',
            currency: String(account.currency ?? '') || '—',
            status: String(account.status ?? '') || '—',
            business_name: String(account.business_name ?? '') || '—',
          })),
    [accounts.rows, recoveryAccounts, showRecoveryFallback],
  );

  const insightsRows = useMemo(() => insights?.rows ?? [], [insights]);
  const campaignsRows = useMemo(() => campaigns?.rows ?? [], [campaigns]);

  const kpis = useMemo(() => sumInsights(insightsRows), [insightsRows]);
  const activeAccounts = useMemo(
    () =>
      (accounts.rows as AccountRow[]).filter((row) => /ACTIVE|^1$/i.test(String(row.status ?? '')))
        .length,
    [accounts.rows],
  );

  const { points: trendPoints, accountIds: trendAccountIds } = useMemo(
    () => groupSpendByDateAccount(insightsRows),
    [insightsRows],
  );

  const accountIdToName = useMemo(() => {
    const map = new Map<string, string>();
    for (const row of accounts.rows as AccountRow[]) {
      const externalId = String(row.external_id ?? '');
      const name = String(row.name ?? '') || externalId;
      if (externalId) map.set(externalId, name);
    }
    return map;
  }, [accounts.rows]);

  const trendSeries: TrendLineSeries[] = useMemo(() => {
    if (!filters.accountId) {
      const top = topAccountsBySpend(insightsRows, TREND_TOP_N);
      return top.map((id) => ({
        key: id,
        label: accountIdToName.get(id) ?? id,
      }));
    }
    // Single-account mode: one series, optionally labelled with account name.
    return [
      {
        key: filters.accountId,
        label: accountIdToName.get(filters.accountId) ?? filters.accountId,
      },
    ];
  }, [filters.accountId, insightsRows, accountIdToName]);

  const peerData = useMemo(() => {
    if (!filters.accountId) return undefined;
    // Suppress when only one account exists in the dataset.
    const unique = new Set<string>();
    for (const row of insightsRows) {
      if (row.account_external_id) unique.add(row.account_external_id);
    }
    if (unique.size < 2) return undefined;
    return computePeerMedian(insightsRows);
  }, [filters.accountId, insightsRows]);

  const pieSlices = useMemo(
    () => spendByObjective(insightsRows, campaignsRows),
    [insightsRows, campaignsRows],
  );

  const kpiTiles: KpiTileProps[] = [
    {
      label: 'Spend',
      value: insightsRows.length ? kpis.spend : null,
      format: 'currency',
      currency: 'USD',
    },
    {
      label: 'Impressions',
      value: insightsRows.length ? kpis.impressions : null,
      format: 'number',
    },
    {
      label: 'Reach',
      value: insightsRows.length ? kpis.reach : null,
      format: 'number',
      hint: 'Aggregate; not deduped',
    },
    { label: 'CTR', value: insightsRows.length ? kpis.ctr : null, format: 'percent' },
    {
      label: 'CPM',
      value: insightsRows.length ? kpis.cpm : null,
      format: 'currency',
      currency: 'USD',
    },
    { label: 'Active accounts', value: activeAccounts, format: 'number' },
  ];

  const accountsLoading = accounts.status === 'loading' && accounts.rows.length === 0;
  const insightsLoading =
    (insights?.status === 'loading' || insights?.status === 'idle') && insightsRows.length === 0;

  // Row click → navigate into Insights scoped to that account.
  const handleRowClick = (row: DisplayAccountRow) => {
    if (showRecoveryFallback) return; // ghost-id guard preserved
    setFilters({ accountId: row.external_id });
    void navigate(`/dashboards/meta/insights?accountId=${encodeURIComponent(row.external_id)}`);
  };

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Meta data</p>
        <h1 className="dashboardHeading">Ad accounts</h1>
        <div className="dashboard-header__actions-row">
          <Link className="button tertiary" to="/dashboards/meta/campaigns">
            Campaign overview
          </Link>
          <Link className="button tertiary" to="/dashboards/meta/insights">
            Insights dashboard
          </Link>
          <Link className="button tertiary" to="/dashboards/meta/status">
            Connection status
          </Link>
          <Link className="button tertiary" to="/dashboards/data-sources?sources=social">
            Connect socials
          </Link>
        </div>
      </header>

      <div className="panel" style={{ marginBottom: '1rem' }}>
        <p className="status-message muted" style={{ margin: 0 }}>
          Meta ad accounts and Facebook Pages are separate assets. JDIC and SLB appear here as ad
          accounts when Meta returns them. Managed Pages remain listed under{' '}
          <Link to="/dashboards/meta/pages">Facebook pages</Link>.
        </p>
      </div>

      <div className="panel" style={{ marginBottom: '1rem' }}>
        <div className="dashboard-header__controls">
          <label className="dashboard-field">
            <span className="dashboard-field__label">Search</span>
            <input
              value={filters.search}
              onChange={(event) => setFilters({ search: event.target.value })}
              placeholder="Name or account id"
            />
          </label>
          <label className="dashboard-field">
            <span className="dashboard-field__label">Status</span>
            <input
              value={filters.status}
              onChange={(event) => setFilters({ status: event.target.value })}
              placeholder="ACTIVE, DISABLED, ..."
            />
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
          <button type="button" className="button secondary" onClick={() => void loadAccounts()}>
            Refresh
          </button>
        </div>
      </div>

      {accounts.status === 'stale' ? (
        <div className="dashboard-state" role="status" style={{ marginBottom: '1rem' }}>
          Showing stale account data.{' '}
          {resolveAccountsErrorMessage(accounts.errorCode, accounts.error)}
        </div>
      ) : null}

      {orphanedMarketingAccess ? (
        <div className="panel meta-warning-panel" role="status" style={{ marginBottom: '1rem' }}>
          <h3>Restore Meta marketing access</h3>
          <p>{metaStatus?.reason.message}</p>
          <div className="dashboard-header__actions-row">
            <Link className="button secondary" to="/dashboards/data-sources?sources=social">
              Restore Meta marketing access
            </Link>
            <Link className="button tertiary" to="/dashboards/meta/status">
              Connection status
            </Link>
          </div>
        </div>
      ) : null}

      {accounts.status === 'error' ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="Unable to load Meta ad accounts"
          message={resolveAccountsErrorMessage(accounts.errorCode, accounts.error)}
          actionLabel="Retry"
          onAction={() => void loadAccounts()}
          className="panel"
          reasonCode="error"
        />
      ) : null}

      {accounts.status !== 'error' &&
      accounts.status !== 'loading' &&
      accounts.rows.length === 0 ? (
        <EmptyState
          icon={<span aria-hidden>0</span>}
          title="No ad accounts yet"
          message={
            showRecoveryFallback
              ? 'Live-discovered Meta ad accounts are available below. Restore marketing access to persist them and restart sync.'
              : orphanedMarketingAccess
                ? 'Meta still has recoverable ad accounts through the stored token. Restore marketing access to persist them and restart sync.'
                : 'Connect Meta and run sync to populate ad accounts.'
          }
          actionLabel={
            orphanedMarketingAccess ? 'Restore Meta marketing access' : 'Connect socials'
          }
          onAction={() => {
            window.location.assign('/dashboards/data-sources?sources=social');
          }}
          className="panel"
          reasonCode="no_accounts"
        />
      ) : null}

      {recoveryStatus === 'loading' && accounts.rows.length === 0 ? (
        <div className="dashboard-state dashboard-state--page">
          Loading recoverable Meta ad accounts...
        </div>
      ) : null}

      {recoveryStatus === 'error' && accounts.rows.length === 0 ? (
        <div className="dashboard-state" role="status" style={{ marginBottom: '1rem' }}>
          {recoveryError ?? 'Unable to preview recoverable Meta ad accounts.'}
        </div>
      ) : null}

      {/* KPI strip */}
      <article className="panel" style={{ marginBottom: '1rem' }} data-testid="meta-accounts-kpis">
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

      {/* Trend + peer-avg */}
      <article className="panel" style={{ marginBottom: '1rem' }}>
        <h3>Spend by account</h3>
        {insightsLoading ? (
          <ChartSkeleton variant="line" height={260} />
        ) : trendPoints.length === 0 || trendAccountIds.length === 0 ? (
          <EmptyState
            icon={<span aria-hidden>0</span>}
            title="No spend data"
            message="No insights in the selected date range."
            reasonCode="no_data_for_range"
          />
        ) : (
          <AccessibleTableToggle
            chartAriaLabel="Spend per account per day"
            chart={
              <TrendLine
                data={trendPoints}
                series={trendSeries}
                peerData={peerData}
                yFormat="currency"
                currency="USD"
                ariaLabel="Spend per account per day"
              />
            }
            table={
              <VizDataTable
                columns={[
                  { accessorKey: 'name', header: 'Account' } as AccountsColumn,
                  { accessorKey: 'external_id', header: 'External ID' } as AccountsColumn,
                ]}
                data={trendAccountIds.map((id) => ({
                  id,
                  name: accountIdToName.get(id) ?? id,
                  external_id: id,
                  account_id: '',
                  currency: '',
                  status: '',
                  business_name: '',
                }))}
                caption="Spend per account per day (tabular)"
                captionHidden
              />
            }
          />
        )}
      </article>

      {/* Pie composition: spend by objective */}
      <article className="panel" style={{ marginBottom: '1rem' }}>
        <h3>Spend by objective</h3>
        {insightsLoading ? (
          <ChartSkeleton variant="pie" height={260} />
        ) : pieSlices.length === 0 ? (
          <EmptyState
            icon={<span aria-hidden>0</span>}
            title="No objective data"
            message="Objective requires both campaigns and insights to be loaded."
            reasonCode="no_data_for_range"
          />
        ) : (
          <AccessibleTableToggle
            chartAriaLabel="Spend by campaign objective"
            chart={
              <PieComposition
                data={pieSlices.map((s) => ({ label: s.label, value: s.value }))}
                yFormat="currency"
                currency="USD"
                ariaLabel="Spend by campaign objective"
              />
            }
            table={
              <VizDataTable
                columns={[
                  { accessorKey: 'name', header: 'Objective' } as AccountsColumn,
                  { accessorKey: 'account_id', header: 'Spend (USD)' } as AccountsColumn,
                ]}
                data={pieSlices.map((s, i) => ({
                  id: `${s.label}-${i}`,
                  name: s.label,
                  external_id: '',
                  account_id: s.value.toFixed(2),
                  currency: 'USD',
                  status: '',
                  business_name: '',
                }))}
                caption="Spend by objective (tabular)"
                captionHidden
              />
            }
          />
        )}
      </article>

      {/* Accounts table */}
      {accountsLoading ? (
        <article className="panel">
          <ChartSkeleton variant="table" rows={5} />
        </article>
      ) : visibleRows.length > 0 ? (
        <article className="panel">
          <div className="panel-header__title-row">
            <h2>Accounts ({displayedAccountCount})</h2>
            {showRecoveryFallback ? (
              <span className="status-pill warning">Live discovered, not yet restored</span>
            ) : null}
          </div>
          <div className="table-responsive">
            <table className="dashboard-table">
              <thead>
                <tr className="dashboard-table__header-row">
                  {accountTableColumns.map((column) => {
                    const header = column.header;
                    const headerLabel =
                      typeof header === 'string'
                        ? header
                        : // Fallback to accessor key if header is a renderer.
                          String((column as unknown as { accessorKey?: string }).accessorKey ?? '');
                    return (
                      <th key={headerLabel} className="dashboard-table__header-cell">
                        {headerLabel}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((account) => (
                  <tr
                    key={account.id}
                    className="dashboard-table__row dashboard-table__row--zebra"
                    style={{ cursor: showRecoveryFallback ? 'default' : 'pointer' }}
                    onClick={() => handleRowClick(account)}
                    aria-label={`Select account ${account.name || account.external_id}`}
                  >
                    <td className="dashboard-table__cell">{account.name || '—'}</td>
                    <td className="dashboard-table__cell">{account.external_id}</td>
                    <td className="dashboard-table__cell">{account.account_id || '—'}</td>
                    <td className="dashboard-table__cell">{account.currency || '—'}</td>
                    <td className="dashboard-table__cell">{account.status || '—'}</td>
                    <td className="dashboard-table__cell">{account.business_name || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      ) : null}
    </section>
  );
};

export default MetaAccountsPage;
