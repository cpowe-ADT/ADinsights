import { useMemo } from 'react';

import { EmptyState, KpiTile, PieComposition } from '../../../viz';
import {
  deriveRecommendationSeverity,
  formatRecommendationImpact,
  groupRecommendationsByType,
  rollupRecommendationKpis,
  type GoogleAdsRecommendationRow,
  type RecommendationSeverity,
} from '../../../../lib/googleAdsAggregates';

type Payload = {
  count?: number;
  results?: GoogleAdsRecommendationRow[];
};

type Props = {
  data: unknown;
  status: 'idle' | 'loading' | 'success' | 'error';
  error: string;
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
    <path d="M12 2l2 7h7l-5.5 4 2 7L12 16l-5.5 4 2-7L3 9h7z" />
  </svg>
);

const SEVERITY_TEXT: Record<RecommendationSeverity, string> = {
  info: 'Info',
  warning: 'Warning',
  danger: 'Danger',
};

const SEVERITY_CHIP_CLASS: Record<RecommendationSeverity, string> = {
  info: 'badge',
  warning: 'badge badge--warning',
  danger: 'badge badge--danger',
};

/**
 * Sprint 3 — Recommendations tab. Architect §6.9.
 *
 * Severity chip derivation fallback (documented for SDK-drift mitigation):
 *   1. `impact_metadata.severity` (canonical; normalized to info/warning/danger)
 *   2. Type heuristic — `recommendation_type` substring match:
 *        BUDGET / BID / PACING → warning
 *        POLICY / DISAPPROVED / SUSPENDED → danger
 *        everything else → info
 * See `deriveRecommendationSeverity` in `lib/googleAdsAggregates.ts`.
 *
 * Dismiss button is suppressed — no backend PATCH endpoint (§3.9).
 */
const RecommendationsTabSection = ({ data, status, error }: Props) => {
  const payload = (data as Payload) ?? {};
  const rows = useMemo(
    () => (Array.isArray(payload.results) ? payload.results : []),
    [payload.results],
  );

  const kpis = useMemo(() => rollupRecommendationKpis(rows), [rows]);
  const typePie = useMemo(() => groupRecommendationsByType(rows), [rows]);

  if (status === 'loading' && rows.length === 0) {
    return <div className="panel">Loading recommendations...</div>;
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
        title="No recommendations"
        message="Google Ads has not surfaced any recommendations for this account in range."
        reasonCode="no_recommendations"
      />
    );
  }

  return (
    <div className="gads-workspace__tab-grid" data-testid="google-ads-recommendations-section">
      <section className="panel">
        <h2>Recommendation KPIs</h2>
        <div
          className="gads-workspace__kpi-grid"
          role="list"
          aria-label="Google Ads recommendation KPIs"
        >
          <KpiTile label="Active" value={kpis.active} format="number" />
          <KpiTile label="Dismissed" value={kpis.dismissed} format="number" />
        </div>
      </section>

      <section className="panel">
        <h2>By recommendation type</h2>
        <PieComposition
          data={typePie}
          yFormat="number"
          ariaLabel="Google Ads recommendations grouped by type"
          emptyReasonCode="no_recommendations"
        />
      </section>

      <section className="panel">
        <h2>Recommendation inventory ({payload.count ?? rows.length})</h2>
        <div className="table-responsive">
          <table className="dashboard-table">
            <thead>
              <tr className="dashboard-table__header-row">
                <th className="dashboard-table__header-cell">Type</th>
                <th className="dashboard-table__header-cell">Campaign</th>
                <th className="dashboard-table__header-cell">Impact</th>
                <th className="dashboard-table__header-cell">Severity</th>
                <th className="dashboard-table__header-cell">Status</th>
                <th className="dashboard-table__header-cell">Last seen</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => {
                const severity = deriveRecommendationSeverity(row);
                const chipClass = SEVERITY_CHIP_CLASS[severity];
                const statusLabel = row.dismissed ? 'Dismissed' : 'Active';
                const statusChip = row.dismissed ? 'badge' : 'badge badge--success';
                const key = `${String(row.resource_name ?? row.campaign_id ?? idx)}-${idx}`;
                return (
                  <tr
                    key={key}
                    className="dashboard-table__row dashboard-table__row--zebra"
                  >
                    <td className="dashboard-table__cell">
                      {row.recommendation_type ?? '—'}
                    </td>
                    <td className="dashboard-table__cell">
                      {row.campaign_id == null ? '—' : String(row.campaign_id)}
                    </td>
                    <td className="dashboard-table__cell">
                      {formatRecommendationImpact(row)}
                    </td>
                    <td className="dashboard-table__cell">
                      <span
                        className={chipClass}
                        data-severity={severity}
                        aria-label={`Severity ${SEVERITY_TEXT[severity]}`}
                      >
                        {SEVERITY_TEXT[severity]}
                      </span>
                    </td>
                    <td className="dashboard-table__cell">
                      <span className={statusChip}>{statusLabel}</span>
                    </td>
                    <td className="dashboard-table__cell">
                      {row.last_seen_at ?? '—'}
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

export default RecommendationsTabSection;
