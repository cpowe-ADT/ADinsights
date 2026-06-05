import { KpiTile } from '../../viz';
import type { KpiFormat } from '../../viz/KpiTile';
import type { SummaryRecord } from './types';

type Props = {
  summary: SummaryRecord | null;
  status: 'idle' | 'loading' | 'success' | 'error';
  error: string;
};

type TileConfig = {
  key: string;
  label: string;
  format: KpiFormat;
};

/**
 * Sprint 3 — WorkspaceKpiStrip now renders the shared `KpiTile` primitive.
 * Architect §4 confirmed Impression Share (IS%) is not available from the
 * API today; this strip therefore ships 4 tiles per the Overview spec
 * plus ROAS and Conv Value for the workspace summary (the extra two are
 * kept only for non-Overview tabs that still read this strip).
 */
const TILES: TileConfig[] = [
  { key: 'spend', label: 'Cost', format: 'currency' },
  { key: 'conversions', label: 'Conversions', format: 'number' },
  { key: 'cpa', label: 'CPA', format: 'currency' },
  { key: 'roas', label: 'ROAS', format: 'number' },
];

const WorkspaceKpiStrip = ({ summary, status, error }: Props) => {
  const isLoading = status === 'loading' && !summary;

  if (status === 'error' && !summary) {
    return (
      <div className="panel" role="alert">
        {error || 'Failed to load workspace summary.'}
      </div>
    );
  }

  const metrics = summary?.metrics ?? {};

  return (
    <div className="panel gads-workspace__kpi-strip" aria-live="polite">
      <div className="gads-workspace__kpi-grid" data-testid="workspace-kpi-grid">
        {TILES.map((tile) => {
          const raw = metrics[tile.key];
          const numeric = raw === null || raw === undefined ? null : Number(raw);
          const value = numeric === null || !Number.isFinite(numeric) ? null : numeric;
          return (
            <KpiTile
              key={tile.key}
              label={tile.label}
              value={value}
              format={tile.format}
              currency="JMD"
              isLoading={isLoading}
              reasonCode={value === null ? 'no_data_for_range' : undefined}
            />
          );
        })}
      </div>
      {summary ? (
        <p className="dashboardSubtitle" style={{ marginTop: '0.75rem' }}>
          Source: {summary.source_engine}
          {summary.data_freshness_ts
            ? ` • Updated ${new Date(summary.data_freshness_ts).toLocaleString()}`
            : ''}
        </p>
      ) : null}
    </div>
  );
};

export default WorkspaceKpiStrip;
