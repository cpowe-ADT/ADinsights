import type { MetaKpi, MetricAvailabilityEntry } from '../lib/metaPageInsights';
import { formatNumber } from '../lib/format';
import MetricAvailabilityBadge from './MetricAvailabilityBadge';

type KPIGridProps = {
  kpis: MetaKpi[];
  metricAvailability: Record<string, MetricAvailabilityEntry>;
};

const KPI_LABELS: Record<string, string> = {
  page_total_media_view_unique: 'Reach (unique media views)',
  page_media_view: 'Media views',
};

function metricLabel(metric: string): string {
  return KPI_LABELS[metric] ?? metric;
}

function DeltaIndicator({ changePct }: { changePct: number }) {
  if (changePct > 0) {
    return <span className="meta-kpi-delta meta-kpi-delta--positive" aria-label="positive change">{'\u25B2'} +{changePct.toFixed(1)}%</span>;
  }
  if (changePct < 0) {
    return <span className="meta-kpi-delta meta-kpi-delta--negative" aria-label="negative change">{'\u25BC'} {changePct.toFixed(1)}%</span>;
  }
  return <span className="meta-kpi-delta meta-kpi-delta--neutral" aria-label="no change">0.0%</span>;
}

const KPIGrid = ({ kpis, metricAvailability }: KPIGridProps) => {
  const visibleKpis = kpis.filter((kpi) => metricAvailability[kpi.metric]?.supported !== false);
  const hiddenCount = kpis.length - visibleKpis.length;

  return (
    <>
      {hiddenCount > 0 ? <p className="meta-warning-text">Some metrics are not available for this Page.</p> : null}
      <section className="meta-kpi-grid-v2" aria-label="Overview KPIs">
        {visibleKpis.map((kpi) => (
          <article className="meta-kpi-card-v2 panel" key={kpi.metric}>
            <p className="meta-kpi-metric">{metricLabel(kpi.metric)}</p>
            <h3 className="meta-kpi-value">{kpi.value == null ? '—' : formatNumber(kpi.value)}</h3>
            <p className="meta-kpi-subvalue">Today: {kpi.today_value == null ? '—' : formatNumber(kpi.today_value)}</p>
            {kpi.change_pct != null ? <DeltaIndicator changePct={kpi.change_pct} /> : null}
            {kpi.prior_value != null ? <p className="meta-kpi-subvalue meta-kpi-prior">Prior: {formatNumber(kpi.prior_value)}</p> : null}
            <MetricAvailabilityBadge metric={kpi.metric} availability={metricAvailability[kpi.metric]} />
          </article>
        ))}
      </section>
    </>
  );
};

export default KPIGrid;
