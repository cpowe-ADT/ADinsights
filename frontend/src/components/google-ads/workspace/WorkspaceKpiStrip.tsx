import type { SummaryRecord } from './types';

type Props = {
  summary: SummaryRecord | null;
  status: 'idle' | 'loading' | 'success' | 'error';
  error: string;
};

const KPI_LABELS: Record<string, string> = {
  spend: 'Spend',
  impressions: 'Impressions',
  clicks: 'Clicks',
  conversions: 'Conversions',
  roas: 'ROAS',
  cpa: 'CPA',
  conversion_value: 'Conv Value',
};

function formatMetric(key: string, value: number): string {
  if (key === 'spend' || key === 'conversion_value' || key === 'cpa') {
    return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  if (key === 'roas') {
    return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  if (key === 'impressions' || key === 'clicks' || key === 'conversions') {
    return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  }
  return value.toFixed(2);
}

const WorkspaceKpiStrip = ({ summary, status, error }: Props) => {
  if (status === 'loading' && !summary) {
    return <div className="panel">Loading workspace summary...</div>;
  }
  if (status === 'error' && !summary) {
    return (
      <div className="panel" role="alert">
        {error}
      </div>
    );
  }
  if (!summary) {
    return null;
  }

  const metricKeys = ['spend', 'clicks', 'conversions', 'roas', 'cpa', 'conversion_value'];

  return (
    <div className="panel gads-workspace__kpi-strip" aria-live="polite">
      <div className="gads-workspace__kpi-grid">
        {metricKeys.map((key) => {
          const raw = Number(summary.metrics[key] ?? 0);
          return (
            <article key={key} className="metric-card metric-card--compact">
              <p className="metric-card__label">{KPI_LABELS[key] ?? key}</p>
              <p className="metric-card__value">{formatMetric(key, raw)}</p>
            </article>
          );
        })}
        <article className="metric-card metric-card--compact">
          <p className="metric-card__label">Pacing status</p>
          <p className="metric-card__value">
            {summary.alerts_summary.overspend_risk
              ? 'Overspend risk'
              : summary.alerts_summary.underdelivery
                ? 'Underdelivery risk'
                : 'On track'}
          </p>
        </article>
      </div>
      <p className="dashboardSubtitle" style={{ marginTop: '0.75rem' }}>
        Source: {summary.source_engine} {summary.data_freshness_ts ? `• Updated ${new Date(summary.data_freshness_ts).toLocaleString()}` : ''}
      </p>
    </div>
  );
};

export default WorkspaceKpiStrip;
