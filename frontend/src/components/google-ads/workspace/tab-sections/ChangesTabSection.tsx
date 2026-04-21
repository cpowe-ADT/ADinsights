import { useMemo } from 'react';

import { DistributionBar, EmptyState, KpiTile } from '../../../viz';
import {
  countChanges7d,
  deriveChangeSeverity,
  groupChangesByResourceType,
  type ChangeSeverity,
  type GoogleAdsChangeRow,
} from '../../../../lib/googleAdsAggregates';

type Payload = {
  count?: number;
  num_pages?: number;
  page?: number;
  page_size?: number;
  results?: GoogleAdsChangeRow[];
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
    <path d="M3 3v18h18" />
    <path d="M7 15l4-4 4 2 5-7" />
  </svg>
);

/**
 * Architect §6.8 — severity chip derivation.
 *
 * Source field: `resource_change_operation`.
 *   CREATE → info      (low-risk, additive)
 *   UPDATE → warning   (attention-worthy, mutation)
 *   REMOVE → danger    (destructive)
 */
const SEVERITY_TEXT: Record<ChangeSeverity, string> = {
  info: 'Info',
  warning: 'Warning',
  danger: 'Danger',
};

const SEVERITY_CHIP_CLASS: Record<ChangeSeverity, string> = {
  info: 'badge',
  warning: 'badge badge--warning',
  danger: 'badge badge--danger',
};

/**
 * Sprint 3 — Changes tab. Architect §6.8.
 *
 * Layout:
 *   1. KpiTile × 2 — Total changes, Changes last 7 days
 *   2. DistributionBar — count by `change_resource_type`
 *   3. Table — Date/Time, User, Resource Type, Operation severity chip,
 *      Campaign, Changed fields (pretty). Chips use text + color so the
 *      encoding is not color-only (WCAG 1.4.1).
 *
 * NB: aggregation covers the current page only; server-side pagination is
 * preserved by consuming `payload.results` verbatim from the hook cache.
 */
const ChangesTabSection = ({ data, status, error }: Props) => {
  const payload = (data as Payload) ?? {};
  const rows = useMemo(
    () => (Array.isArray(payload.results) ? payload.results : []),
    [payload.results],
  );

  const totalCount = typeof payload.count === 'number' ? payload.count : rows.length;
  const last7d = useMemo(() => countChanges7d(rows), [rows]);
  const typeBars = useMemo(() => groupChangesByResourceType(rows), [rows]);

  if (status === 'loading' && rows.length === 0) {
    return <div className="panel">Loading change events...</div>;
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
        title="No change events"
        message="No recent Google Ads account changes in this range."
        reasonCode="no_change_events"
      />
    );
  }

  const formatChangedFields = (value: unknown): string => {
    if (value == null) return '—';
    if (Array.isArray(value)) return value.join(', ');
    if (typeof value === 'object') {
      try {
        const json = JSON.stringify(value);
        return json.length > 80 ? `${json.slice(0, 77)}…` : json;
      } catch {
        return '—';
      }
    }
    return String(value);
  };

  return (
    <div className="gads-workspace__tab-grid" data-testid="google-ads-changes-section">
      <section className="panel">
        <h2>Change KPIs</h2>
        <div
          className="gads-workspace__kpi-grid"
          role="list"
          aria-label="Google Ads change KPIs"
        >
          <KpiTile label="Total changes" value={totalCount} format="number" />
          <KpiTile label="Changes last 7 days" value={last7d} format="number" />
        </div>
      </section>

      <section className="panel">
        <h2>Changes by resource type</h2>
        <DistributionBar
          data={typeBars}
          yFormat="number"
          ariaLabel="Google Ads changes grouped by resource type"
          emptyReasonCode="no_change_events"
        />
      </section>

      <section className="panel">
        <h2>Change log ({totalCount})</h2>
        <div className="table-responsive">
          <table className="dashboard-table">
            <thead>
              <tr className="dashboard-table__header-row">
                <th className="dashboard-table__header-cell">Date/Time</th>
                <th className="dashboard-table__header-cell">User</th>
                <th className="dashboard-table__header-cell">Resource</th>
                <th className="dashboard-table__header-cell">Operation</th>
                <th className="dashboard-table__header-cell">Campaign</th>
                <th className="dashboard-table__header-cell">Changed fields</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => {
                const severity = deriveChangeSeverity(row.resource_change_operation);
                const chipClass = SEVERITY_CHIP_CLASS[severity];
                const key = `${String(row.customer_id ?? '')}-${String(row.change_date_time ?? idx)}-${idx}`;
                return (
                  <tr
                    key={key}
                    className="dashboard-table__row dashboard-table__row--zebra"
                  >
                    <td className="dashboard-table__cell">{row.change_date_time ?? '—'}</td>
                    <td className="dashboard-table__cell">{row.user_email ?? '—'}</td>
                    <td className="dashboard-table__cell">
                      {row.change_resource_type ?? '—'}
                    </td>
                    <td className="dashboard-table__cell">
                      <span
                        className={chipClass}
                        data-severity={severity}
                        aria-label={`Severity ${SEVERITY_TEXT[severity]}`}
                      >
                        {row.resource_change_operation ?? '—'}
                        <span className="sr-only"> — {SEVERITY_TEXT[severity]}</span>
                      </span>
                    </td>
                    <td className="dashboard-table__cell">
                      {row.campaign_id == null ? '—' : String(row.campaign_id)}
                    </td>
                    <td className="dashboard-table__cell">
                      {formatChangedFields(row.changed_fields)}
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

export default ChangesTabSection;
