import { useCallback, useEffect, useMemo, useState } from 'react';

import { EmptyState, KpiTile, PieComposition } from '../../../viz';
import {
  deriveRecommendationSeverity,
  formatRecommendationImpact,
  groupRecommendationsByType,
  rollupRecommendationKpis,
  type GoogleAdsRecommendationRow,
  type RecommendationSeverity,
} from '../../../../lib/googleAdsAggregates';
import { dismissGoogleAdsRecommendation } from '../../../../lib/googleAdsDashboard';
import { useToastStore } from '../../../../stores/useToastStore';

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
 * GA-A2: Status cell renders a Dismiss button for non-dismissed rows;
 * dismissed rows show the existing chip. Click does an optimistic local
 * update, then fires POST .../dismiss/; on failure the local state is
 * rolled back and an error toast is emitted.
 */
const RecommendationsTabSection = ({ data, status, error }: Props) => {
  const payload = (data as Payload) ?? {};
  const sourceRows = useMemo(
    () => (Array.isArray(payload.results) ? payload.results : []),
    [payload.results],
  );

  const [rows, setRows] = useState<GoogleAdsRecommendationRow[]>(sourceRows);
  const [pendingIds, setPendingIds] = useState<Set<number>>(new Set());
  const addToast = useToastStore((s) => s.addToast);

  // Keep local rows in sync when the parent supplies new data. Because we
  // replace the full array on refresh the optimistic state resets too — that
  // is the desired behavior (the server is the source of truth on refresh).
  useEffect(() => {
    setRows(sourceRows);
  }, [sourceRows]);

  const handleDismiss = useCallback(
    async (row: GoogleAdsRecommendationRow) => {
      const id = typeof row.id === 'number' ? row.id : Number(row.id);
      if (!Number.isFinite(id) || id <= 0) {
        addToast('Recommendation cannot be dismissed (missing id).', 'error');
        return;
      }
      // Optimistic update.
      setRows((prev) => prev.map((r) => (r.id === id ? { ...r, dismissed: true } : r)));
      setPendingIds((prev) => {
        const next = new Set(prev);
        next.add(id);
        return next;
      });
      try {
        await dismissGoogleAdsRecommendation(id);
        addToast('Recommendation dismissed');
      } catch (err) {
        // Rollback + toast error.
        setRows((prev) => prev.map((r) => (r.id === id ? { ...r, dismissed: false } : r)));
        const msg = err instanceof Error ? err.message : 'Failed to dismiss recommendation.';
        addToast(msg, 'error');
      } finally {
        setPendingIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }
    },
    [addToast],
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
                const numericId = typeof row.id === 'number' ? row.id : Number(row.id);
                const hasValidId = Number.isFinite(numericId) && numericId > 0;
                const isPending = hasValidId ? pendingIds.has(numericId) : false;
                const key = `${String(row.resource_name ?? row.campaign_id ?? idx)}-${idx}`;
                return (
                  <tr key={key} className="dashboard-table__row dashboard-table__row--zebra">
                    <td className="dashboard-table__cell">{row.recommendation_type ?? '—'}</td>
                    <td className="dashboard-table__cell">
                      {row.campaign_id == null ? '—' : String(row.campaign_id)}
                    </td>
                    <td className="dashboard-table__cell">{formatRecommendationImpact(row)}</td>
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
                      {row.dismissed ? (
                        <span className="badge" data-status="dismissed">
                          Dismissed
                        </span>
                      ) : hasValidId ? (
                        <button
                          type="button"
                          className="button tertiary"
                          onClick={() => {
                            void handleDismiss(row);
                          }}
                          disabled={isPending}
                          data-action="dismiss-recommendation"
                          data-recommendation-id={numericId}
                        >
                          Dismiss
                        </button>
                      ) : (
                        <span className="badge badge--success">Active</span>
                      )}
                    </td>
                    <td className="dashboard-table__cell">{row.last_seen_at ?? '—'}</td>
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
