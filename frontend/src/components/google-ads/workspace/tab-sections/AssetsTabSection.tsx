import { useMemo } from 'react';

import { EmptyState, KpiTile, PieComposition } from '../../../viz';
import { resolveSeriesColor } from '../../../../styles/chartTheme';
import {
  buildAssetHeatGrid,
  buildAssetTypePie,
  rollupAssetKpis,
  type GoogleAdsAssetRow,
} from '../../../../lib/googleAdsCreativeConvAggregates';

type Payload = {
  count?: number;
  results?: GoogleAdsAssetRow[];
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
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M3 10h18" />
    <path d="M9 4v16" />
  </svg>
);

const STATUS_CHIP_CLASSES: Record<string, string> = {
  APPROVED: 'badge badge--success',
  DISAPPROVED: 'badge badge--danger',
  AREA_OF_INTEREST_ONLY: 'badge badge--warning',
  UNKNOWN: 'badge',
};

const TONE_CLASS: Record<string, string> = {
  low: 'gads-heat-cell--low',
  medium: 'gads-heat-cell--medium',
  high: 'gads-heat-cell--high',
};

/**
 * Sprint 3 — Assets tab. Architect §6.4.
 *
 * Heat-tinted asset grid is rendered INLINE per architect §5 decision
 * matrix: per-asset daily series is not available so the kit-primitive
 * investment is unwarranted. The tint is driven by conversion rate
 * (single-metric heat) with tone chips providing non-color threshold
 * encoding.
 */
const AssetsTabSection = ({ data, status, error }: Props) => {
  const payload = (data as Payload) ?? {};
  const rows = useMemo(
    () => (Array.isArray(payload.results) ? payload.results : []),
    [payload.results],
  );

  const kpis = useMemo(() => rollupAssetKpis(rows), [rows]);
  const typePie = useMemo(
    () => buildAssetTypePie(rows).map((p) => ({ label: p.label, value: p.value })),
    [rows],
  );
  const heatGrid = useMemo(() => buildAssetHeatGrid(rows), [rows]);
  const baseColor = resolveSeriesColor(0);

  if (status === 'loading' && rows.length === 0) {
    return <div className="panel">Loading assets...</div>;
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
        title="No assets in range"
        message="Adjust the date range or customer filter to see ad assets."
        reasonCode="no_assets"
      />
    );
  }

  return (
    <div className="gads-workspace__tab-grid" data-testid="google-ads-assets-section">
      <section className="panel">
        <h2>Asset KPIs</h2>
        <div className="gads-workspace__kpi-grid" role="list" aria-label="Google Ads asset KPIs">
          <KpiTile label="Total Assets" value={kpis.total} format="number" />
          <KpiTile
            label="Disapproved"
            value={kpis.disapproved}
            format="number"
            reasonCode={kpis.disapproved === 0 ? 'no_assets' : undefined}
          />
          <KpiTile label="Top Asset Conv" value={kpis.topAssetConv} format="number" />
        </div>
      </section>

      <section className="panel">
        <h2>Asset type mix</h2>
        {typePie.length === 0 ? (
          <EmptyState
            icon={<EmptyIcon />}
            title="No asset-type breakdown"
            message="No assets returned an asset_type."
            reasonCode="no_assets"
          />
        ) : (
          <PieComposition
            data={typePie}
            yFormat="number"
            ariaLabel="Assets by asset type"
            emptyReasonCode="no_assets"
          />
        )}
      </section>

      <section className="panel">
        <h2>Asset heat map</h2>
        <p className="dashboardSubtitle">
          Shaded by conversion rate (darker = higher). Per-asset daily trend is not available from
          the Google Ads API today; tone chips ensure the encoding is not color-only.
        </p>
        <ul
          className="gads-heat-grid"
          role="list"
          aria-label="Asset conversion rate heat grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
            gap: 12,
            listStyle: 'none',
            padding: 0,
          }}
        >
          {heatGrid.map((cell) => (
            <li
              key={cell.id}
              className={`panel gads-heat-cell ${TONE_CLASS[cell.tone] ?? ''}`}
              style={{
                background: baseColor,
                backgroundImage: `linear-gradient(180deg, rgba(255,255,255,${
                  1 - Math.min(0.85, cell.intensity)
                }) 0%, rgba(255,255,255,${1 - Math.min(0.85, cell.intensity)}) 100%)`,
                padding: 12,
              }}
              data-tone={cell.tone}
            >
              <div
                style={{
                  fontWeight: 600,
                  fontSize: 13,
                  color: '#0f172a',
                  marginBottom: 4,
                }}
              >
                {cell.title}
              </div>
              <div style={{ fontSize: 11, color: '#334155', marginBottom: 8 }}>{cell.subtitle}</div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span
                  className="badge"
                  data-tone={cell.tone}
                  aria-label={`Heat level ${cell.tone}`}
                >
                  {cell.tone}
                </span>
                <span style={{ fontSize: 12, color: '#0f172a' }}>
                  {(cell.convRate * 100).toFixed(1)}% conv rate
                </span>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <h2>Asset performance ({payload.count ?? rows.length})</h2>
        <div className="table-responsive">
          <table className="dashboard-table">
            <thead>
              <tr className="dashboard-table__header-row">
                <th className="dashboard-table__header-cell">Asset Type</th>
                <th className="dashboard-table__header-cell">Asset ID</th>
                <th className="dashboard-table__header-cell">Impressions</th>
                <th className="dashboard-table__header-cell">Clicks</th>
                <th className="dashboard-table__header-cell">Conv</th>
                <th className="dashboard-table__header-cell">CPA</th>
                <th className="dashboard-table__header-cell">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => {
                const key = String(row.asset_id ?? `row-${idx}`);
                const status = (row.policy_approval_status ?? 'UNKNOWN').toString();
                const chip =
                  STATUS_CHIP_CLASSES[status.toUpperCase()] ?? STATUS_CHIP_CLASSES.UNKNOWN;
                return (
                  <tr key={key} className="dashboard-table__row dashboard-table__row--zebra">
                    <td className="dashboard-table__cell">{row.asset_type ?? '—'}</td>
                    <td className="dashboard-table__cell">{key}</td>
                    <td className="dashboard-table__cell">
                      {Number(row.impressions ?? 0).toFixed(0)}
                    </td>
                    <td className="dashboard-table__cell">{Number(row.clicks ?? 0).toFixed(0)}</td>
                    <td className="dashboard-table__cell">
                      {Number(row.conversions ?? 0).toFixed(2)}
                    </td>
                    <td className="dashboard-table__cell">{Number(row.cpa ?? 0).toFixed(2)}</td>
                    <td className="dashboard-table__cell">
                      <span className={chip}>{status}</span>
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

export default AssetsTabSection;
