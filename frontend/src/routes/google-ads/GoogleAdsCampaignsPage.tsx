import { useEffect, useMemo, useState } from 'react';

import {
  BubbleScatter,
  DistributionBar,
  EmptyState,
  KpiTile,
} from '../../components/viz';
import {
  buildCampaignBubblePoints,
  buildTopSpendBars,
  deriveCampaignStatusTone,
  rollupCampaignKpis,
  type GoogleAdsCampaignRow,
} from '../../lib/googleAdsAggregates';
import {
  fetchGoogleAdsList,
  type GoogleAdsListResponse,
} from '../../lib/googleAdsDashboard';
import { appendQueryParams } from '../../lib/apiClient';
import { resolveFilterRange } from '../../lib/dashboardFilters';
import useDashboardStore from '../../state/useDashboardStore';

const EmptyIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M3 10h18" />
  </svg>
);

const STATUS_CHIP_CLASSES: Record<string, string> = {
  success: 'badge badge--success',
  warning: 'badge badge--warning',
  danger: 'badge badge--danger',
  neutral: 'badge',
};

/**
 * Sprint 3 — legacy Campaigns page. Matches the unified-mode
 * CampaignsTabSection layout (KPI strip, BubbleScatter, top-10 bar,
 * table) per architect §6.2. Replaces the generic GoogleAdsDataTablePage
 * wrapper since per-campaign viz transforms cannot be generic.
 */
const GoogleAdsCampaignsPage = () => {
  const [payload, setPayload] = useState<GoogleAdsListResponse<GoogleAdsCampaignRow>>({
    count: 0,
    results: [],
  });
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('loading');
  const [error, setError] = useState('');
  const filters = useDashboardStore((state) => state.filters);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setStatus('loading');
      setError('');
      try {
        const { start, end } = resolveFilterRange(filters);
        const path = appendQueryParams('/analytics/google-ads/campaigns/', {
          platforms: 'google_ads',
          customer_id: filters.accountId || undefined,
          start_date: start || undefined,
          end_date: end || undefined,
        });
        const response = await fetchGoogleAdsList<GoogleAdsCampaignRow>(path);
        if (!active) return;
        setPayload(response);
        setStatus('idle');
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Failed to load campaigns.');
        setStatus('error');
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [filters]);

  const rows = payload.results;
  const kpis = useMemo(() => rollupCampaignKpis(rows), [rows]);
  const bubbles = useMemo(() => buildCampaignBubblePoints(rows), [rows]);
  const topSpend = useMemo(() => buildTopSpendBars(rows, 10), [rows]);

  return (
    <section className="dashboardPage">
      <header className="dashboardPageHeader">
        <p className="dashboardEyebrow">Google Ads</p>
        <h1 className="dashboardHeading">Performance by Campaign</h1>
        <p className="dashboardSubtitle">
          Campaign-level metrics with pagination, sorting, and server-side aggregation.
        </p>
      </header>

      {status === 'loading' ? (
        <div className="dashboard-state dashboard-state--page">Loading campaigns...</div>
      ) : null}
      {status === 'error' ? (
        <div className="dashboard-state dashboard-state--page" role="alert">
          {error}
        </div>
      ) : null}

      {status !== 'loading' && rows.length === 0 ? (
        <EmptyState
          icon={<EmptyIcon />}
          title="No campaigns in range"
          message="Adjust the date range or customer filter to see campaign performance."
          reasonCode="no_campaigns"
        />
      ) : null}

      {rows.length > 0 ? (
        <>
          <div className="panel" style={{ marginBottom: '1rem' }}>
            <h2>Campaign KPIs</h2>
            <div
              className="gads-workspace__kpi-grid"
              role="list"
              aria-label="Google Ads campaign KPIs"
            >
              <KpiTile label="Total Cost" value={kpis.totalSpend} format="currency" currency="JMD" />
              <KpiTile label="Total Conversions" value={kpis.totalConversions} format="number" />
              <KpiTile label="Avg CPA" value={kpis.avgCpa} format="currency" currency="JMD" />
              <KpiTile label="Avg ROAS" value={kpis.avgRoas} format="number" />
            </div>
          </div>

          <div className="panel" style={{ marginBottom: '1rem' }}>
            <h2>Cost vs. conversion rate</h2>
            <BubbleScatter
              data={bubbles}
              xLabel="Cost"
              yLabel="Conversion rate"
              zLabel="Impressions"
              xFormat="currency"
              yFormat="percent"
              zFormat="number"
              currency="JMD"
              ariaLabel="Campaign cost vs conversion rate bubble scatter"
              emptyReasonCode="no_campaigns"
            />
          </div>

          <div className="panel" style={{ marginBottom: '1rem' }}>
            <h2>Top 10 campaigns by cost</h2>
            <DistributionBar
              data={topSpend}
              yFormat="currency"
              currency="JMD"
              ariaLabel="Top 10 Google Ads campaigns by cost"
              emptyReasonCode="no_campaigns"
            />
          </div>

          <div className="panel">
            <h2>
              Results ({payload.count ?? rows.length})
              {payload.source_engine ? (
                <span className="dashboard-field__label" style={{ marginLeft: '0.75rem' }}>
                  Source: {payload.source_engine}
                </span>
              ) : null}
            </h2>
            <div className="table-responsive">
              <table className="dashboard-table">
                <thead>
                  <tr className="dashboard-table__header-row">
                    <th className="dashboard-table__header-cell">Campaign</th>
                    <th className="dashboard-table__header-cell">Status</th>
                    <th className="dashboard-table__header-cell">Channel</th>
                    <th className="dashboard-table__header-cell">Cost</th>
                    <th className="dashboard-table__header-cell">Clicks</th>
                    <th className="dashboard-table__header-cell">Impr</th>
                    <th className="dashboard-table__header-cell">Conv</th>
                    <th className="dashboard-table__header-cell">CPA</th>
                    <th className="dashboard-table__header-cell">ROAS</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, idx) => {
                    const tone = deriveCampaignStatusTone(row.campaign_status);
                    return (
                      <tr
                        key={String(row.campaign_id ?? idx)}
                        className="dashboard-table__row dashboard-table__row--zebra"
                      >
                        <td className="dashboard-table__cell">
                          {row.campaign_name ?? row.campaign_id ?? '—'}
                        </td>
                        <td className="dashboard-table__cell">
                          <span
                            className={STATUS_CHIP_CLASSES[tone] ?? STATUS_CHIP_CLASSES.neutral}
                            data-status-tone={tone}
                          >
                            {row.campaign_status ?? '—'}
                          </span>
                        </td>
                        <td className="dashboard-table__cell">{row.channel_type ?? '—'}</td>
                        <td className="dashboard-table__cell">{Number(row.spend ?? 0).toFixed(2)}</td>
                        <td className="dashboard-table__cell">{Number(row.clicks ?? 0).toFixed(0)}</td>
                        <td className="dashboard-table__cell">{Number(row.impressions ?? 0).toFixed(0)}</td>
                        <td className="dashboard-table__cell">{Number(row.conversions ?? 0).toFixed(2)}</td>
                        <td className="dashboard-table__cell">{Number(row.cpa ?? 0).toFixed(2)}</td>
                        <td className="dashboard-table__cell">{Number(row.roas ?? 0).toFixed(2)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
};

export default GoogleAdsCampaignsPage;
