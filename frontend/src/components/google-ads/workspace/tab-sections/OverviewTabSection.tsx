import { useMemo } from 'react';

import { EmptyState, PieComposition, TrendLine, KpiTile } from '../../../viz';
import {
  buildChannelPie,
  deriveTrendSeries,
  rollupOverviewKpis,
  type GoogleAdsCampaignRow,
} from '../../../../lib/googleAdsAggregates';
import type { SummaryRecord } from '../types';

type Props = {
  summary: SummaryRecord | null;
  /**
   * Campaigns-tab cache — the architect §4 audit confirmed that the
   * channel pie is derived from campaign rows, not from the workspace
   * summary. When the campaigns cache has not been loaded, we render an
   * EmptyState with reasonCode=no_data_for_range in the pie slot.
   */
  campaignRows?: GoogleAdsCampaignRow[] | null;
};

const EmptyIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="40"
    height="40"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    aria-hidden="true"
  >
    <circle cx="12" cy="12" r="10" />
    <path d="M8 12h8" />
  </svg>
);

/**
 * Sprint 3 — Overview tab. Replaces three raw HTML tables with the
 * Sprint-1 viz kit. Architect §4 confirmed Impression Share (IS%) is
 * not exposed by the API today, so this ships 4 KPI tiles instead of 5.
 */
const OverviewTabSection = ({ summary, campaignRows }: Props) => {
  const kpis = useMemo(() => rollupOverviewKpis(summary), [summary]);
  const trendPoints = useMemo(() => deriveTrendSeries(summary?.trend), [summary?.trend]);
  const channelPie = useMemo(() => buildChannelPie(campaignRows), [campaignRows]);

  if (!summary) {
    return (
      <EmptyState
        icon={<EmptyIcon />}
        title="Loading overview..."
        message="Workspace summary is loading."
        reasonCode="no_data_for_range"
      />
    );
  }

  return (
    <div className="gads-workspace__tab-grid" data-testid="google-ads-overview-section">
      <section className="panel">
        <h2>Performance snapshot</h2>
        <div className="gads-workspace__kpi-grid" role="list" aria-label="Google Ads overview KPIs">
          <KpiTile label="Cost" value={kpis.spend} format="currency" currency="JMD" />
          <KpiTile label="Conversions" value={kpis.conversions} format="number" />
          <KpiTile label="CPA" value={kpis.cpa} format="currency" currency="JMD" />
          <KpiTile label="ROAS" value={kpis.roas} format="number" />
        </div>
        {/* IS% intentionally deferred — architect §4. */}
      </section>

      <section className="panel">
        <h2>Cost &amp; Conversions trend</h2>
        <TrendLine
          data={trendPoints}
          series={[
            { key: 'spend', label: 'Cost', yAxis: 'left' },
            { key: 'conversions', label: 'Conversions', yAxis: 'right' },
          ]}
          yFormat="currency"
          rightYFormat="number"
          ariaLabel="Cost and conversions daily trend"
          emptyReasonCode="no_data_for_range"
        />
      </section>

      <section className="panel">
        <h2>Cost by channel</h2>
        {channelPie.length === 0 ? (
          <EmptyState
            icon={<EmptyIcon />}
            title="No channel breakdown available"
            message="Load the Campaigns tab to see cost-by-channel distribution."
            reasonCode="no_data_for_range"
          />
        ) : (
          <PieComposition
            data={channelPie}
            yFormat="currency"
            currency="JMD"
            ariaLabel="Google Ads cost by channel type"
            emptyReasonCode="no_data_for_range"
          />
        )}
      </section>

      <section className="panel">
        <h2>Top movers</h2>
        <div className="table-responsive">
          <table className="dashboard-table">
            <thead>
              <tr className="dashboard-table__header-row">
                <th className="dashboard-table__header-cell">Campaign</th>
                <th className="dashboard-table__header-cell">Cost</th>
                <th className="dashboard-table__header-cell">Conv value</th>
                <th className="dashboard-table__header-cell">ROAS</th>
              </tr>
            </thead>
            <tbody>
              {summary.movers.map((row) => (
                <tr
                  key={String(row.campaign_id)}
                  className="dashboard-table__row dashboard-table__row--zebra"
                >
                  <td className="dashboard-table__cell">
                    {String(row.campaign_name ?? row.campaign_id)}
                  </td>
                  <td className="dashboard-table__cell">{Number(row.spend ?? 0).toFixed(2)}</td>
                  <td className="dashboard-table__cell">
                    {Number(row.conversion_value ?? 0).toFixed(2)}
                  </td>
                  <td className="dashboard-table__cell">{Number(row.roas ?? 0).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

export default OverviewTabSection;
