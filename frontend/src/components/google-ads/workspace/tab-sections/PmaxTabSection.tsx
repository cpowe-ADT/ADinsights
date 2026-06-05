import { useMemo } from 'react';

import { AssetGroupTreemap, EmptyState, KpiTile } from '../../../viz';
import {
  buildPmaxTreemapData,
  rollupPmaxKpis,
  type GoogleAdsAssetGroupRow,
} from '../../../../lib/googleAdsCreativeConvAggregates';

type Payload = {
  count?: number;
  results?: GoogleAdsAssetGroupRow[];
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
    <rect x="3" y="3" width="8" height="8" rx="1" />
    <rect x="13" y="3" width="8" height="5" rx="1" />
    <rect x="13" y="10" width="8" height="11" rx="1" />
    <rect x="3" y="13" width="8" height="8" rx="1" />
  </svg>
);

const STATUS_CHIP_CLASSES: Record<string, string> = {
  ENABLED: 'badge badge--success',
  ACTIVE: 'badge badge--success',
  PAUSED: 'badge badge--warning',
  REMOVED: 'badge badge--danger',
  UNKNOWN: 'badge',
};

/**
 * Sprint 3 — PMax tab. Architect §6.5.
 *
 * KPI strip + AssetGroupTreemap (new viz-kit primitive) + VizDataTable.
 */
const PmaxTabSection = ({ data, status, error }: Props) => {
  const payload = (data as Payload) ?? {};
  const rows = useMemo(
    () => (Array.isArray(payload.results) ? payload.results : []),
    [payload.results],
  );

  const kpis = useMemo(() => rollupPmaxKpis(rows), [rows]);
  const treemapData = useMemo(() => buildPmaxTreemapData(rows), [rows]);

  if (status === 'loading' && rows.length === 0) {
    return <div className="panel">Loading Performance Max asset groups...</div>;
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
        title="No Performance Max asset groups"
        message="This customer has no PMax asset groups in the selected range."
        reasonCode="no_pmax_groups"
      />
    );
  }

  return (
    <div className="gads-workspace__tab-grid" data-testid="google-ads-pmax-section">
      <section className="panel">
        <h2>Performance Max KPIs</h2>
        <div className="gads-workspace__kpi-grid" role="list" aria-label="Google Ads PMax KPIs">
          <KpiTile label="Total Asset Groups" value={kpis.totalGroups} format="number" />
          <KpiTile label="Total Cost" value={kpis.totalCost} format="currency" currency="JMD" />
          <KpiTile label="Total Conv" value={kpis.totalConversions} format="number" />
        </div>
      </section>

      <section className="panel">
        <h2>Asset-group spend treemap</h2>
        <p className="dashboardSubtitle">
          Rectangle area = spend. Shading = ROAS (darker = higher, hatched = under-performing).
          Refer to the accessible table below for the underlying values.
        </p>
        <AssetGroupTreemap
          data={treemapData}
          currency="JMD"
          ariaLabel="Performance Max asset groups by spend"
          emptyReasonCode="no_pmax_groups"
        />
      </section>

      <section className="panel">
        <h2>Asset group performance ({payload.count ?? rows.length})</h2>
        <div className="table-responsive">
          <table className="dashboard-table">
            <thead>
              <tr className="dashboard-table__header-row">
                <th className="dashboard-table__header-cell">Asset Group</th>
                <th className="dashboard-table__header-cell">Status</th>
                <th className="dashboard-table__header-cell">Cost</th>
                <th className="dashboard-table__header-cell">Impressions</th>
                <th className="dashboard-table__header-cell">Conv</th>
                <th className="dashboard-table__header-cell">CPA</th>
                <th className="dashboard-table__header-cell">ROAS</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => {
                const key = String(row.asset_group_id ?? `row-${idx}`);
                const status = (row.asset_group_status ?? 'UNKNOWN').toString();
                const chip =
                  STATUS_CHIP_CLASSES[status.toUpperCase()] ?? STATUS_CHIP_CLASSES.UNKNOWN;
                return (
                  <tr key={key} className="dashboard-table__row dashboard-table__row--zebra">
                    <td className="dashboard-table__cell">{row.asset_group_name ?? key}</td>
                    <td className="dashboard-table__cell">
                      <span className={chip}>{status}</span>
                    </td>
                    <td className="dashboard-table__cell">{Number(row.spend ?? 0).toFixed(2)}</td>
                    <td className="dashboard-table__cell">
                      {Number(row.impressions ?? 0).toFixed(0)}
                    </td>
                    <td className="dashboard-table__cell">
                      {Number(row.conversions ?? 0).toFixed(2)}
                    </td>
                    <td className="dashboard-table__cell">{Number(row.cpa ?? 0).toFixed(2)}</td>
                    <td className="dashboard-table__cell">{Number(row.roas ?? 0).toFixed(2)}</td>
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

export default PmaxTabSection;
