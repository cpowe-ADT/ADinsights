import { useMemo } from 'react';

import { DistributionBar, EmptyState, KpiTile, PieComposition } from '../../../viz';
import {
  buildConvActionPie,
  buildFunnelStages,
  rollupConversionKpis,
  type GoogleAdsConversionActionRow,
} from '../../../../lib/googleAdsCreativeConvAggregates';
import type { SummaryRecord } from '../types';

type Payload = {
  count?: number;
  results?: GoogleAdsConversionActionRow[];
};

type Props = {
  data: unknown;
  status: 'idle' | 'loading' | 'success' | 'error';
  error: string;
  /** Workspace summary — funnel reads metrics.{impressions,clicks,conversions}. */
  summary: SummaryRecord | null;
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
    <path d="M3 3h18l-8 10v6l-2 1v-7z" />
  </svg>
);

/**
 * Sprint 3 — Conversions tab. Architect §6.6.
 *
 * Funnel-via-DistributionBar: the primitive has no first-class funnel
 * rendering; the architect's decision (matching Sprint 2 Meta Campaigns
 * precedent) is to feed the ordered funnel stages into `DistributionBar`
 * as-is. The array order IS the funnel order, and `DistributionBar`
 * respects input order in both layouts.
 */
const ConversionsTabSection = ({ data, status, error, summary }: Props) => {
  const payload = (data as Payload) ?? {};
  const rows = useMemo(
    () => (Array.isArray(payload.results) ? payload.results : []),
    [payload.results],
  );

  const kpis = useMemo(() => rollupConversionKpis(rows), [rows]);
  const funnelStages = useMemo(
    () => buildFunnelStages(summary?.metrics),
    [summary?.metrics],
  );
  const sourceMix = useMemo(() => buildConvActionPie(rows), [rows]);

  if (status === 'loading' && rows.length === 0) {
    return <div className="panel">Loading conversions...</div>;
  }
  if (status === 'error' && rows.length === 0) {
    return (
      <div className="panel" role="alert">
        {error}
      </div>
    );
  }

  const hasAnyFunnelValue = funnelStages.some((s) => s.value > 0);

  if (rows.length === 0 && !hasAnyFunnelValue) {
    return (
      <EmptyState
        icon={<EmptyIcon />}
        title="No conversion data"
        message="There are no conversions for the selected range."
        reasonCode="no_conversions"
      />
    );
  }

  return (
    <div
      className="gads-workspace__tab-grid"
      data-testid="google-ads-conversions-section"
    >
      <section className="panel">
        <h2>Conversion KPIs</h2>
        <div
          className="gads-workspace__kpi-grid"
          role="list"
          aria-label="Google Ads conversion KPIs"
        >
          <KpiTile
            label="Total Conversions"
            value={kpis.totalConversions}
            format="number"
          />
          <KpiTile
            label="Total Value"
            value={kpis.totalValue}
            format="currency"
            currency="JMD"
          />
          <KpiTile
            label="Avg CPA"
            value={kpis.avgCpa}
            format="currency"
            currency="JMD"
          />
        </div>
      </section>

      <section className="panel">
        <h2>Funnel: Impressions → Clicks → Conversions</h2>
        <p className="dashboardSubtitle">
          Stage order is preserved. Rendered via the shared DistributionBar
          primitive (Sprint 2 Meta Campaigns precedent).
        </p>
        <DistributionBar
          data={funnelStages}
          orientation="horizontal"
          yFormat="number"
          ariaLabel="Google Ads conversion funnel stages"
          emptyReasonCode="no_conversions"
        />
      </section>

      <section className="panel">
        <h2>Source mix by conversion action</h2>
        {sourceMix.length === 0 ? (
          <EmptyState
            icon={<EmptyIcon />}
            title="No conversion-action mix"
            message="No conversion actions reported conversions."
            reasonCode="no_conversions"
          />
        ) : (
          <PieComposition
            data={sourceMix}
            yFormat="number"
            ariaLabel="Conversions by action name"
            emptyReasonCode="no_conversions"
          />
        )}
      </section>

      <section className="panel">
        <h2>Conversion actions ({payload.count ?? rows.length})</h2>
        <div className="table-responsive">
          <table className="dashboard-table">
            <thead>
              <tr className="dashboard-table__header-row">
                <th className="dashboard-table__header-cell">Action Name</th>
                <th className="dashboard-table__header-cell">Conversions</th>
                <th className="dashboard-table__header-cell">Value</th>
                <th className="dashboard-table__header-cell">CPA</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => {
                const key = String(row.conversion_action_id ?? `row-${idx}`);
                return (
                  <tr
                    key={key}
                    className="dashboard-table__row dashboard-table__row--zebra"
                  >
                    <td className="dashboard-table__cell">
                      {row.conversion_action_name ?? '—'}
                    </td>
                    <td className="dashboard-table__cell">
                      {Number(row.conversions ?? 0).toFixed(2)}
                    </td>
                    <td className="dashboard-table__cell">
                      {Number(row.value ?? row.conversion_value ?? 0).toFixed(2)}
                    </td>
                    <td className="dashboard-table__cell">
                      {Number(row.cpa ?? 0).toFixed(2)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

export default ConversionsTabSection;
