import { useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { ColumnDef } from '@tanstack/react-table';

import EmptyState from '../components/EmptyState';
import {
  AccessibleTableToggle,
  DistributionBar,
  KpiTile,
  Sparkline,
  VizDataTable,
} from '../components/viz';
import useMetaStore from '../state/useMetaStore';
import type { MetaCampaign, MetaInsightRecord } from '../lib/meta';

function resolveCampaignsErrorMessage(errorCode?: string, fallback?: string): string {
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

function pct(numerator: number, denominator: number): string {
  if (!denominator) return '0%';
  return `${((numerator / denominator) * 100).toFixed(1)}%`;
}

type CampaignRow = {
  id: string;
  name: string;
  externalId: string;
  status: string;
  objective: string;
  account: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  updated: string;
  spendSpark: Array<{ date: string; value: number }>;
};

const MetaCampaignOverviewPage = () => {
  const { filters, setFilters, accounts, campaigns, insights, loadAccounts, loadCampaigns, loadInsights } =
    useMetaStore((state) => ({
      filters: state.filters,
      setFilters: state.setFilters,
      accounts: state.accounts,
      campaigns: state.campaigns,
      insights: state.insights,
      loadAccounts: state.loadAccounts,
      loadCampaigns: state.loadCampaigns,
      loadInsights: state.loadInsights,
    }));

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);

  // Ensure insights fetch uses campaign level while this page is mounted.
  useEffect(() => {
    if (filters.level !== 'campaign') {
      setFilters({ level: 'campaign' });
    }
  }, [filters.level, setFilters]);

  useEffect(() => {
    void loadCampaigns();
  }, [
    filters.accountId,
    filters.search,
    filters.status,
    filters.since,
    filters.until,
    loadCampaigns,
  ]);

  useEffect(() => {
    if (filters.level !== 'campaign') {
      return;
    }
    void loadInsights();
  }, [
    filters.level,
    filters.accountId,
    filters.since,
    filters.until,
    filters.status,
    loadInsights,
  ]);

  const activeCount = useMemo(
    () => campaigns.rows.filter((row) => row.status.toUpperCase().includes('ACTIVE')).length,
    [campaigns.rows],
  );

  // --- Aggregate totals + funnel stages ---
  const totals = useMemo(() => {
    return insights.rows.reduce(
      (acc, row) => {
        acc.impressions += Number(row.impressions) || 0;
        acc.clicks += Number(row.clicks) || 0;
        acc.conversions += Number(row.conversions) || 0;
        acc.spend += Number(row.spend) || 0;
        return acc;
      },
      { impressions: 0, clicks: 0, conversions: 0, spend: 0 },
    );
  }, [insights.rows]);

  // Funnel-as-DistributionBar: ordered stages, descending values preserved.
  const funnelStages = useMemo(
    () => [
      { label: 'Impressions', value: totals.impressions },
      { label: 'Clicks', value: totals.clicks },
      { label: 'Conversions', value: totals.conversions },
    ],
    [totals],
  );

  // Spend by campaign, top 10.
  const insightsByCampaign = useMemo(() => {
    const grouped = new Map<string, MetaInsightRecord[]>();
    insights.rows.forEach((row) => {
      const cid = row.campaign_external_id || row.external_id;
      if (!cid) return;
      const bucket = grouped.get(cid) ?? [];
      bucket.push(row);
      grouped.set(cid, bucket);
    });
    return grouped;
  }, [insights.rows]);

  const campaignNameByExternalId = useMemo(() => {
    const map = new Map<string, string>();
    campaigns.rows.forEach((c: MetaCampaign) => {
      map.set(c.external_id, c.name || c.external_id);
    });
    return map;
  }, [campaigns.rows]);

  const topSpend = useMemo(() => {
    const entries = Array.from(insightsByCampaign.entries()).map(([cid, rows]) => ({
      label: campaignNameByExternalId.get(cid) ?? cid,
      value: rows.reduce((sum, r) => sum + (Number(r.spend) || 0), 0),
    }));
    return entries
      .filter((entry) => entry.value > 0)
      .sort((a, b) => b.value - a.value)
      .slice(0, 10);
  }, [insightsByCampaign, campaignNameByExternalId]);

  // Inline per-row sparkline series (spend over time).
  const sparklineByCampaign = useMemo(() => {
    const map = new Map<string, Array<{ date: string; value: number }>>();
    insightsByCampaign.forEach((rows, cid) => {
      const sorted = [...rows]
        .filter((r) => r.date)
        .sort((a, b) => a.date.localeCompare(b.date));
      map.set(
        cid,
        sorted.map((r) => ({ date: r.date, value: Number(r.spend) || 0 })),
      );
    });
    return map;
  }, [insightsByCampaign]);

  const tableRows: CampaignRow[] = useMemo(
    () =>
      campaigns.rows.map((campaign) => {
        const rows = insightsByCampaign.get(campaign.external_id) ?? [];
        const spend = rows.reduce((s, r) => s + (Number(r.spend) || 0), 0);
        const impressions = rows.reduce((s, r) => s + (Number(r.impressions) || 0), 0);
        const clicks = rows.reduce((s, r) => s + (Number(r.clicks) || 0), 0);
        const conversions = rows.reduce((s, r) => s + (Number(r.conversions) || 0), 0);
        return {
          id: campaign.id,
          name: campaign.name,
          externalId: campaign.external_id,
          status: campaign.status || '—',
          objective: campaign.objective || '—',
          account: campaign.account_external_id || '—',
          spend,
          impressions,
          clicks,
          conversions,
          updated: campaign.updated_time || campaign.updated_at,
          spendSpark: sparklineByCampaign.get(campaign.external_id) ?? [],
        };
      }),
    [campaigns.rows, insightsByCampaign, sparklineByCampaign],
  );

  const vizColumns = useMemo<ColumnDef<CampaignRow, unknown>[]>(
    () => [
      { accessorKey: 'name', header: 'Campaign' },
      { accessorKey: 'status', header: 'Status' },
      { accessorKey: 'objective', header: 'Objective' },
      { accessorKey: 'account', header: 'Account' },
      { accessorKey: 'spend', header: 'Spend' },
      { accessorKey: 'impressions', header: 'Impressions' },
      { accessorKey: 'clicks', header: 'Clicks' },
      { accessorKey: 'conversions', header: 'Conversions' },
      {
        id: 'spendTrend',
        header: 'Spend trend (14d)',
        cell: ({ row }) => {
          const sparkline = row.original.spendSpark.slice(-14);
          if (sparkline.length === 0) {
            return <span data-testid="campaign-spend-spark-empty">—</span>;
          }
          return (
            <span data-testid="campaign-spend-spark">
              <Sparkline
                data={sparkline}
                ariaLabel={`${row.original.name} spend trend`}
                height={32}
              />
            </span>
          );
        },
      },
      { accessorKey: 'updated', header: 'Updated' },
    ],
    [],
  );

  const funnelTooltipLabels = useMemo(() => {
    return {
      ctr: pct(totals.clicks, totals.impressions),
      cvr: pct(totals.conversions, totals.clicks),
    };
  }, [totals]);

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Meta data</p>
        <h1 className="dashboardHeading">Campaign overview</h1>
        <div className="dashboard-header__actions-row">
          <Link className="button tertiary" to="/dashboards/meta/accounts">
            Account list
          </Link>
          <Link className="button tertiary" to="/dashboards/meta/insights">
            Insights dashboard
          </Link>
        </div>
      </header>

      <div className="dashboard-grid" data-testid="meta-campaigns-kpi-strip" style={{ marginBottom: '1rem' }}>
        <KpiTile
          label="Spend"
          value={totals.spend > 0 ? totals.spend : null}
          format="currency"
          reasonCode="meta_campaigns_spend"
        />
        <KpiTile
          label="Impressions"
          value={totals.impressions > 0 ? totals.impressions : null}
          format="number"
          reasonCode="meta_campaigns_impressions"
        />
        <KpiTile
          label="Clicks"
          value={totals.clicks > 0 ? totals.clicks : null}
          format="number"
          reasonCode="meta_campaigns_clicks"
        />
        <KpiTile
          label="Conversions"
          value={totals.conversions > 0 ? totals.conversions : null}
          format="number"
          reasonCode="meta_campaigns_conversions"
        />
      </div>

      <div className="panel" style={{ marginBottom: '1rem' }}>
        <div className="dashboard-header__controls">
          <label className="dashboard-field">
            <span className="dashboard-field__label">Account</span>
            <select
              value={filters.accountId}
              onChange={(event) =>
                setFilters({
                  accountId: event.target.value,
                  campaignId: '',
                  adsetId: '',
                })
              }
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
            <span className="dashboard-field__label">Status</span>
            <input
              value={filters.status}
              onChange={(event) => setFilters({ status: event.target.value })}
              placeholder="ACTIVE / PAUSED"
            />
          </label>
          <label className="dashboard-field">
            <span className="dashboard-field__label">Search</span>
            <input
              value={filters.search}
              onChange={(event) => setFilters({ search: event.target.value })}
              placeholder="Campaign name"
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
          <button type="button" className="button secondary" onClick={() => void loadCampaigns()}>
            Refresh
          </button>
        </div>
      </div>

      {/* Funnel visualised as an ordered DistributionBar — architect §4.3 decision. */}
      <article className="panel" data-testid="meta-campaigns-funnel-panel" style={{ marginBottom: '1rem' }}>
        <h3>Funnel</h3>
        <p className="muted">
          Impressions → Clicks ({funnelTooltipLabels.ctr} CTR) → Conversions ({funnelTooltipLabels.cvr} CVR)
        </p>
        <AccessibleTableToggle
          chartAriaLabel="Campaign funnel: impressions, clicks, conversions"
          chart={
            <DistributionBar
              data={funnelStages}
              orientation="horizontal"
              ariaLabel="Campaign funnel"
              height={220}
              emptyReasonCode="no_data_for_range"
            />
          }
          table={
            <table className="dashboard-table">
              <thead>
                <tr>
                  <th className="dashboard-table__header-cell">Stage</th>
                  <th className="dashboard-table__header-cell">Count</th>
                </tr>
              </thead>
              <tbody>
                {funnelStages.map((stage) => (
                  <tr key={stage.label}>
                    <td className="dashboard-table__cell">{stage.label}</td>
                    <td className="dashboard-table__cell">{stage.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          }
        />
      </article>

      <article className="panel" data-testid="meta-campaigns-spend-panel" style={{ marginBottom: '1rem' }}>
        <h3>Spend by campaign (top 10)</h3>
        <AccessibleTableToggle
          chartAriaLabel="Top 10 campaigns by spend"
          chart={
            <DistributionBar
              data={topSpend}
              orientation="horizontal"
              yFormat="currency"
              ariaLabel="Top 10 campaigns by spend"
              height={Math.max(160, topSpend.length * 28)}
              emptyReasonCode="no_data_for_range"
            />
          }
          table={
            <table className="dashboard-table">
              <thead>
                <tr>
                  <th className="dashboard-table__header-cell">Campaign</th>
                  <th className="dashboard-table__header-cell">Spend</th>
                </tr>
              </thead>
              <tbody>
                {topSpend.map((row) => (
                  <tr key={row.label}>
                    <td className="dashboard-table__cell">{row.label}</td>
                    <td className="dashboard-table__cell">{row.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          }
        />
      </article>

      <div className="dashboard-state muted" style={{ marginBottom: '0.5rem' }}>
        {campaigns.count} total campaigns · {activeCount} active
      </div>

      {campaigns.status === 'loading' && campaigns.rows.length === 0 ? (
        <div className="dashboard-state dashboard-state--page">Loading campaigns...</div>
      ) : null}

      {campaigns.status === 'stale' ? (
        <div className="dashboard-state" role="status" style={{ marginBottom: '1rem' }}>
          Showing stale campaign data.{' '}
          {resolveCampaignsErrorMessage(campaigns.errorCode, campaigns.error)}
        </div>
      ) : null}

      {campaigns.status === 'error' ? (
        <EmptyState
          icon={<span aria-hidden>!</span>}
          title="Unable to load campaigns"
          message={resolveCampaignsErrorMessage(campaigns.errorCode, campaigns.error)}
          actionLabel="Retry"
          onAction={() => void loadCampaigns()}
          className="panel"
          reasonCode="error"
        />
      ) : null}

      {campaigns.status !== 'error' && campaigns.status !== 'loading' && campaigns.rows.length === 0 ? (
        <EmptyState
          icon={<span aria-hidden>0</span>}
          title="No campaigns found"
          message="Try different filters or run hierarchy sync."
          className="panel"
          reasonCode="no_campaigns"
        />
      ) : null}

      {campaigns.rows.length > 0 ? (
        <article className="panel" data-testid="meta-campaigns-table-panel">
          <VizDataTable
            columns={vizColumns}
            data={tableRows}
            ariaLabel="Meta campaigns"
            caption="Meta campaigns with insights rollup"
            captionHidden
            csvFilename="meta-campaigns.csv"
            getRowId={(row) => row.id}
          />
        </article>
      ) : null}
    </section>
  );
};

export default MetaCampaignOverviewPage;
