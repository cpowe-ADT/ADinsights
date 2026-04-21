import { useMemo } from 'react';

import {
  BubbleScatter,
  DistributionBar,
  EmptyState,
  KpiTile,
} from '../../../viz';
import {
  buildCampaignBubblePoints,
  buildTopSpendBars,
  deriveCampaignStatusTone,
  rollupCampaignKpis,
  type GoogleAdsCampaignRow,
} from '../../../../lib/googleAdsAggregates';

type Payload = {
  count?: number;
  results?: GoogleAdsCampaignRow[];
};

type Props = {
  data: unknown;
  status: 'idle' | 'loading' | 'success' | 'error';
  error: string;
  drawerCampaignId: string;
  onOpenDrawer: (campaignId: string) => void;
  onCloseDrawer: () => void;
};

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

const CampaignsTabSection = ({
  data,
  status,
  error,
  drawerCampaignId,
  onOpenDrawer,
  onCloseDrawer,
}: Props) => {
  const payload = (data as Payload) ?? {};
  const rows = useMemo(
    () => (Array.isArray(payload.results) ? payload.results : []),
    [payload.results],
  );

  const kpis = useMemo(() => rollupCampaignKpis(rows), [rows]);
  const bubbles = useMemo(() => buildCampaignBubblePoints(rows), [rows]);
  const topSpend = useMemo(() => buildTopSpendBars(rows, 10), [rows]);

  if (status === 'loading' && rows.length === 0) {
    return <div className="panel">Loading campaigns...</div>;
  }
  if (status === 'error' && rows.length === 0) {
    return (
      <div className="panel" role="alert">
        {error}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <EmptyState
        icon={<EmptyIcon />}
        title="No campaigns in range"
        message="Adjust the date range or customer filter to see campaign performance."
        reasonCode="no_campaigns"
      />
    );
  }

  const selected = rows.find((row) => String(row.campaign_id ?? '') === drawerCampaignId) ?? null;

  return (
    <div
      className="gads-workspace__tab-grid gads-workspace__tab-grid--with-drawer"
      data-testid="google-ads-campaigns-section"
    >
      <section className="panel">
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
      </section>

      <section className="panel">
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
      </section>

      <section className="panel">
        <h2>Top 10 campaigns by cost</h2>
        <p className="dashboardSubtitle">
          Per-campaign daily trend is not yet available from the API; this bar
          chart serves as the top-10 overview fallback.
        </p>
        <DistributionBar
          data={topSpend}
          yFormat="currency"
          currency="JMD"
          ariaLabel="Top 10 Google Ads campaigns by cost"
          emptyReasonCode="no_campaigns"
        />
      </section>

      <section className="panel">
        <h2>Campaign performance ({payload.count ?? rows.length})</h2>
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
              {rows.map((row) => {
                const campaignId = String(row.campaign_id ?? '');
                const tone = deriveCampaignStatusTone(row.campaign_status);
                return (
                  <tr
                    key={campaignId || row.campaign_name}
                    className="dashboard-table__row dashboard-table__row--zebra"
                  >
                    <td className="dashboard-table__cell">
                      <button
                        type="button"
                        className="button tertiary"
                        onClick={() => onOpenDrawer(campaignId)}
                        disabled={!campaignId}
                        aria-label={`Open campaign details for ${row.campaign_name ?? campaignId}`}
                      >
                        {row.campaign_name ?? campaignId}
                      </button>
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
      </section>

      <aside className="panel gads-workspace__drawer" aria-live="polite">
        <div className="gads-workspace__drawer-head">
          <h3>Campaign drilldown</h3>
          <button type="button" className="button tertiary" onClick={onCloseDrawer}>
            Close
          </button>
        </div>
        {!selected ? <p className="muted">Select a campaign row to inspect details.</p> : null}
        {selected ? (
          <dl className="gads-workspace__keyvals">
            <dt>Campaign</dt>
            <dd>{selected.campaign_name ?? selected.campaign_id ?? '—'}</dd>
            <dt>Status</dt>
            <dd>{selected.campaign_status ?? '—'}</dd>
            <dt>Cost</dt>
            <dd>{Number(selected.spend ?? 0).toFixed(2)}</dd>
            <dt>Clicks</dt>
            <dd>{Number(selected.clicks ?? 0).toFixed(0)}</dd>
            <dt>Impressions</dt>
            <dd>{Number(selected.impressions ?? 0).toFixed(0)}</dd>
            <dt>Conversions</dt>
            <dd>{Number(selected.conversions ?? 0).toFixed(2)}</dd>
            <dt>CPA</dt>
            <dd>{Number(selected.cpa ?? 0).toFixed(2)}</dd>
            <dt>ROAS</dt>
            <dd>{Number(selected.roas ?? 0).toFixed(2)}</dd>
          </dl>
        ) : null}
      </aside>
    </div>
  );
};

export default CampaignsTabSection;
