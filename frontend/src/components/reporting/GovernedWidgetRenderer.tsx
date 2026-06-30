import type { ColumnDef } from '@tanstack/react-table';

import { DistributionBar, KpiTile, TrendLine, VizDataTable } from '../viz';
import type { TrendLinePoint, TrendLineSeries } from '../viz/TrendLine';
import type { DashboardWidgetCoverage, DashboardWidgetPreviewResponse } from '../../lib/phase2Api';

type TableRow = Record<string, unknown>;

const titleFromWidget = (widget: DashboardWidgetPreviewResponse): string =>
  String((widget.data?.title as string | undefined) || widget.widget_id.replace(/_/g, ' '));

const labelFromKey = (key: string): string =>
  key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .trim();

const numberValue = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const formatForMetric = (metric: string): 'currency' | 'number' | 'percent' | 'rate' => {
  if (['spend', 'cpc', 'cpm', 'cpa', 'conversion_value'].includes(metric)) {
    return 'currency';
  }
  if (['ctr', 'roas', 'frequency'].includes(metric)) {
    return 'rate';
  }
  return 'number';
};

const coverageTone = (coverage: DashboardWidgetCoverage | null): string => {
  const status = coverage?.coverage_status ?? 'blocked';
  if (status === 'fresh') {
    return 'fresh';
  }
  if (['stale', 'partial', 'source_disconnected'].includes(status)) {
    return 'stale';
  }
  return 'failed';
};

const widgetStatusLabel = (widget: DashboardWidgetPreviewResponse): string => {
  if (widget.status === 'blocked' || widget.status === 'error') {
    return widget.status;
  }
  if (widget.coverage?.coverage_status && widget.coverage.coverage_status !== 'fresh') {
    return widget.coverage.coverage_status;
  }
  return widget.status ?? 'rendered';
};

const widgetStatusTone = (widget: DashboardWidgetPreviewResponse): string => {
  if (widget.status === 'blocked' || widget.status === 'error') {
    return 'failed';
  }
  return widget.coverage ? coverageTone(widget.coverage) : 'fresh';
};

const CoverageNote = ({ coverage }: { coverage: DashboardWidgetCoverage | null }) => {
  if (!coverage) {
    return <p className="phase2-note">Preview blocked before coverage could be computed.</p>;
  }
  return (
    <div className="reporting-coverage-note">
      <span className={`phase2-pill phase2-pill--${coverageTone(coverage)}`}>
        {coverage.coverage_status}
      </span>
      <span>{coverage.coverage_note}</span>
    </div>
  );
};

const KpiPreview = ({ widget }: { widget: DashboardWidgetPreviewResponse }) => {
  const metrics = Array.isArray(widget.data.metrics)
    ? (widget.data.metrics as Array<Record<string, unknown>>)
    : [];
  return (
    <div className="metrics-grid reporting-widget__kpis">
      {metrics.map((metric) => {
        const key = String(metric.key ?? metric.label ?? '');
        return (
          <KpiTile
            key={key}
            label={String(metric.label ?? labelFromKey(key))}
            value={numberValue(metric.value)}
            format={formatForMetric(key)}
            hint={widget.coverage?.source_label ?? widget.dataset}
          />
        );
      })}
    </div>
  );
};

const LinePreview = ({ widget }: { widget: DashboardWidgetPreviewResponse }) => {
  const rows = Array.isArray(widget.data.rows) ? (widget.data.rows as TableRow[]) : [];
  const metricKeys = rows.length
    ? Object.keys(rows[0]).filter(
        (key) => key !== 'date' && key !== String(widget.data.x ?? 'date'),
      )
    : [];
  const series: TrendLineSeries[] = metricKeys.map((key) => ({
    key,
    label: labelFromKey(key),
  }));
  const data: TrendLinePoint[] = rows.map((row) => ({
    date: String(row.date ?? row[String(widget.data.x ?? 'date')] ?? ''),
    ...Object.fromEntries(metricKeys.map((key) => [key, numberValue(row[key])])),
  }));
  return (
    <TrendLine
      data={data}
      series={series}
      ariaLabel={`${titleFromWidget(widget)} trend`}
      yFormat={formatForMetric(metricKeys[0] ?? '') === 'currency' ? 'currency' : 'number'}
    />
  );
};

const BarPreview = ({ widget }: { widget: DashboardWidgetPreviewResponse }) => {
  const rows = Array.isArray(widget.data.rows) ? (widget.data.rows as TableRow[]) : [];
  const xKey = String(widget.data.x ?? 'label');
  const metricKey =
    rows.length > 0 ? (Object.keys(rows[0]).find((key) => key !== xKey) ?? 'value') : 'value';
  const data = rows.flatMap((row) => {
    const value = numberValue(row[metricKey]);
    return value === null
      ? []
      : [
          {
            label: String(row[xKey] ?? row.label ?? 'Unspecified'),
            value,
          },
        ];
  });
  return (
    <DistributionBar
      data={data}
      ariaLabel={`${titleFromWidget(widget)} bar chart`}
      yFormat={formatForMetric(metricKey) === 'currency' ? 'currency' : 'number'}
    />
  );
};

const TablePreview = ({ widget }: { widget: DashboardWidgetPreviewResponse }) => {
  const rows = Array.isArray(widget.data.rows) ? (widget.data.rows as TableRow[]) : [];
  const columnKeys = Array.isArray(widget.data.columns)
    ? (widget.data.columns as string[])
    : rows.length
      ? Object.keys(rows[0])
      : [];
  const columns: ColumnDef<TableRow, unknown>[] = columnKeys.map((key) => ({
    accessorKey: key,
    header: labelFromKey(key),
  }));
  return (
    <VizDataTable
      columns={columns}
      data={rows}
      caption={`Stored aggregate rows for ${titleFromWidget(widget)}`}
      emptyMessage="No stored aggregate rows are available for this widget."
    />
  );
};

const ReportSectionPreview = ({ widget }: { widget: DashboardWidgetPreviewResponse }) => (
  <div className="reporting-section-copy">
    <p>
      {String(widget.data?.body || '') ||
        'This section is part of the governed SLB report scaffold and inherits the report coverage notes.'}
    </p>
  </div>
);

export const GovernedWidgetRenderer = ({ widget }: { widget: DashboardWidgetPreviewResponse }) => {
  const title = titleFromWidget(widget);
  const blocked = widget.status === 'blocked' || widget.status === 'error';
  const statusLabel = widgetStatusLabel(widget);

  return (
    <article className="phase2-card reporting-widget" data-widget-id={widget.widget_id}>
      <div className="reporting-widget__header">
        <div>
          <p className="dashboardEyebrow">{widget.dataset}</p>
          <h3>{title}</h3>
        </div>
        <span className={`phase2-pill phase2-pill--${widgetStatusTone(widget)}`}>
          {statusLabel}
        </span>
      </div>
      {blocked ? (
        <DashboardWidgetError widget={widget} />
      ) : widget.type === 'kpi' ? (
        <KpiPreview widget={widget} />
      ) : widget.type === 'line_chart' ? (
        <LinePreview widget={widget} />
      ) : widget.type === 'bar_chart' || widget.type === 'stacked_bar_chart' ? (
        <BarPreview widget={widget} />
      ) : widget.type === 'data_table' ? (
        <TablePreview widget={widget} />
      ) : widget.type === 'report_section' ? (
        <ReportSectionPreview widget={widget} />
      ) : (
        <p className="phase2-note">Unsupported governed widget type: {widget.type}</p>
      )}
      <CoverageNote coverage={widget.coverage} />
      {widget.warnings.length > 0 ? (
        <ul className="reporting-widget__warnings">
          {widget.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
    </article>
  );
};

const DashboardWidgetError = ({ widget }: { widget: DashboardWidgetPreviewResponse }) => (
  <div className="reporting-widget__error">
    <strong>{widget.status === 'blocked' ? 'Blocked' : 'Preview failed'}</strong>
    <p>{widget.error || widget.warnings[0] || 'This widget could not be rendered.'}</p>
  </div>
);

export default GovernedWidgetRenderer;
