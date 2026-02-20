import type { MetaMetricOption } from '../../lib/metaPageInsights';

type MetricPickerProps = {
  metrics: MetaMetricOption[];
  selectedMetric: string;
  showAllMetrics: boolean;
  onMetricChange: (metric: string) => void;
  onToggleAllMetrics: (showAll: boolean) => void;
};

function isVisibleInDefault(option: MetaMetricOption): boolean {
  return option.status === 'ACTIVE' || option.status === 'UNKNOWN';
}

const MetricPicker = ({
  metrics,
  selectedMetric,
  showAllMetrics,
  onMetricChange,
  onToggleAllMetrics,
}: MetricPickerProps) => {
  const visibleMetrics = showAllMetrics ? metrics : metrics.filter(isVisibleInDefault);

  return (
    <div className="meta-controls-row">
      <label className="dashboard-field meta-metric-picker">
        <span className="dashboard-field__label">Metric</span>
        <select value={selectedMetric} onChange={(event) => onMetricChange(event.target.value)}>
          {visibleMetrics.map((metric) => (
            <option key={metric.metric_key} value={metric.metric_key}>
              {metric.metric_key}
              {metric.status === 'INVALID' ? ' (invalid)' : ''}
              {metric.status === 'DEPRECATED' ? ' (deprecated)' : ''}
            </option>
          ))}
        </select>
      </label>
      <label className="meta-toggle-all">
        <input
          type="checkbox"
          checked={showAllMetrics}
          onChange={(event) => onToggleAllMetrics(event.target.checked)}
        />
        <span>All metrics</span>
      </label>
      {metrics
        .filter((metric) => metric.status === 'INVALID' || metric.status === 'DEPRECATED')
        .slice(0, 1)
        .map((metric) => (
          <p key={metric.metric_key} className="meta-warning-chip" role="status">
            {metric.metric_key} is {metric.status.toLowerCase()}
            {metric.replacement_metric_key ? `, try ${metric.replacement_metric_key}.` : '.'}
          </p>
        ))}
    </div>
  );
};

export default MetricPicker;
