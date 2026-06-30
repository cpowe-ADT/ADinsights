import type {
  DashboardWidgetCoverage,
  DashboardWidgetPreviewResponse,
  ReportDataAvailabilityResponse,
  ReportMetricAvailabilityEntry,
  ReportPreviewResponse,
  ReportingCatalogMetric,
  ReportingCatalogResponse,
} from '../../lib/phase2Api';

import {
  DEFAULT_GRID_COLS,
  DEFAULT_ROW_HEIGHT,
  type DashboardLayoutConfig,
  type DashboardWidget,
  type TableColumn,
  type WidgetOptions,
  type WidgetSourceBinding,
  widgetSourceSignature,
} from './layoutSchema';

type TableRow = Record<string, unknown>;
const NON_METRIC_ROW_KEYS = new Set([
  'ad',
  'ad_account',
  'adset',
  'campaign',
  'channel',
  'client',
  'content',
  'content_type',
  'creative',
  'date',
  'label',
  'month',
  'objective',
  'page',
  'parish',
  'period',
  'permalink',
  'placement',
  'platform',
  'post',
  'published_post',
  'reaction_type',
  'region',
  'source',
  'status',
  'week',
  'workspace',
]);

const metricFormat = (metric: string): WidgetOptions['format'] => {
  if (['spend', 'cpc', 'cpm', 'cpa', 'conversion_value'].includes(metric)) {
    return 'currency';
  }
  if (['ctr', 'roas', 'frequency'].includes(metric)) {
    return 'rate';
  }
  return 'number';
};

const lineFormat = (metric: string): WidgetOptions['yFormat'] =>
  metricFormat(metric) === 'currency' ? 'currency' : 'number';

const labelFromKey = (key: string): string =>
  key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .trim();

const availabilityDatasetForMetric = (dataset: string, metric: string): string => {
  if (dataset === 'organic_facebook_page' && metric.startsWith('post_')) {
    return 'organic_facebook_posts';
  }
  return dataset;
};

const numberValue = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const titleFromWidget = (widget: DashboardWidgetPreviewResponse): string =>
  String(widget.data?.title || widget.widget_id.replace(/_/g, ' '));

const coverageText = (coverage: DashboardWidgetCoverage | null): string =>
  coverage?.coverage_note ? `\n\n${coverage.coverage_note}` : '';

const sourceFromWidget = (
  widget: DashboardWidgetPreviewResponse,
  metrics: string[] = [],
): WidgetSourceBinding => ({
  dataset: widget.dataset,
  widgetId: widget.widget_id,
  metrics,
});

const availabilityFromMetric = (
  metric: ReportingCatalogMetric,
  availability: ReportDataAvailabilityResponse | null,
): ReportMetricAvailabilityEntry | null => {
  const dataset = availabilityDatasetForMetric(metric.dataset, metric.key);
  const entries = availability?.datasets[dataset]?.metric_availability?.metrics ?? [];
  return entries.find((entry) => entry.key === metric.key) ?? null;
};

const metricAvailabilityForWidget = (
  metric: ReportingCatalogMetric,
  availability: ReportDataAvailabilityResponse | null,
): WidgetSourceBinding['availability'] => {
  const runtime = availabilityFromMetric(metric, availability);
  return [
    {
      key: metric.key,
      state: runtime?.availability_state ?? metric.availability_state ?? 'available',
      note: runtime?.availability_note ?? metric.availability_note,
      rowCount: runtime?.row_count,
    },
  ];
};

const rowsFromWidget = (widget: DashboardWidgetPreviewResponse): TableRow[] =>
  Array.isArray(widget.data.rows) ? (widget.data.rows as TableRow[]) : [];

const metricKeysFromRows = (rows: TableRow[], xKey: string): string[] => {
  const first = rows[0];
  if (!first) return [];
  return Object.keys(first).filter((key) => key !== xKey && key !== 'date');
};

const metricKeysFromWidget = (widget: DashboardWidgetPreviewResponse, xKey: string): string[] => {
  const declared = Array.isArray(widget.metrics)
    ? widget.metrics.map(String).filter((key) => key.length > 0)
    : [];
  if (declared.length > 0) return declared;
  return metricKeysFromRows(rowsFromWidget(widget), xKey).filter(
    (key) => !NON_METRIC_ROW_KEYS.has(key),
  );
};

const columnsFromWidget = (widget: DashboardWidgetPreviewResponse): TableColumn[] => {
  const rows = rowsFromWidget(widget);
  const keys = Array.isArray(widget.data.columns)
    ? (widget.data.columns as string[])
    : rows.length > 0
      ? Object.keys(rows[0])
      : [];
  return keys.map((key) => ({
    key,
    header: labelFromKey(key),
    align: rows.some((row) => numberValue(row[key]) !== null) ? 'right' : 'left',
  }));
};

const blockedNote = (widget: DashboardWidgetPreviewResponse): Omit<DashboardWidget, 'x' | 'y'> => {
  const reason = widget.error || widget.warnings[0] || 'This governed widget is not renderable.';
  return {
    id: `${widget.widget_id}-note`,
    type: 'note',
    title: titleFromWidget(widget),
    w: 12,
    h: 2,
    source: sourceFromWidget(widget),
    options: {
      text: `${reason}${coverageText(widget.coverage)}`.trim(),
    },
  };
};

function widgetsFromPreviewWidget(
  widget: DashboardWidgetPreviewResponse,
): Array<Omit<DashboardWidget, 'x' | 'y'>> {
  if (widget.status === 'blocked' || widget.status === 'error') {
    return [blockedNote(widget)];
  }

  if (widget.type === 'report_section') {
    return [
      {
        id: widget.widget_id,
        type: 'note',
        title: titleFromWidget(widget),
        w: 12,
        h: 2,
        source: sourceFromWidget(widget),
        options: {
          text:
            String(widget.data.body || '') ||
            `${titleFromWidget(widget)}${coverageText(widget.coverage)}`.trim(),
        },
      },
    ];
  }

  if (widget.type === 'kpi') {
    const metrics = Array.isArray(widget.data.metrics)
      ? (widget.data.metrics as Array<Record<string, unknown>>)
      : [];
    return metrics.map((metric) => {
      const key = String(metric.key ?? metric.label ?? widget.widget_id);
      return {
        id: `${widget.widget_id}-${key}`,
        type: 'kpi',
        title: String(metric.label ?? labelFromKey(key)),
        w: 3,
        h: 2,
        data: numberValue(metric.value),
        source: sourceFromWidget(widget, [key]),
        options: { format: metricFormat(key), currency: 'JMD' },
      };
    });
  }

  if (widget.type === 'line_chart') {
    const rows = rowsFromWidget(widget);
    const xKey = String(widget.data.x || 'date');
    const metricKeys = metricKeysFromWidget(widget, xKey);
    const data = rows.map((row) => ({
      date: String(row[xKey] ?? row.date ?? ''),
      ...Object.fromEntries(metricKeys.map((key) => [key, numberValue(row[key])])),
    }));
    return [
      {
        id: widget.widget_id,
        type: 'line',
        title: titleFromWidget(widget),
        w: 12,
        h: 4,
        data,
        source: sourceFromWidget(widget, metricKeys),
        options: {
          height: 220,
          series: metricKeys.map((key) => ({ key, label: labelFromKey(key) })),
          yFormat: lineFormat(metricKeys[0] ?? ''),
          currency: 'JMD',
        },
      },
    ];
  }

  if (widget.type === 'bar_chart' || widget.type === 'stacked_bar_chart') {
    const rows = rowsFromWidget(widget);
    const xKey = String(widget.data.x || 'label');
    const metricKey = metricKeysFromWidget(widget, xKey)[0] ?? 'value';
    return [
      {
        id: widget.widget_id,
        type: 'bar',
        title: titleFromWidget(widget),
        w: 12,
        h: 4,
        source: sourceFromWidget(widget, [metricKey]),
        data: rows.flatMap((row) => {
          const value = numberValue(row[metricKey]);
          return value === null
            ? []
            : [{ label: String(row[xKey] ?? row.label ?? 'Unspecified'), value }];
        }),
        options: {
          height: 220,
          currency: metricFormat(metricKey) === 'currency' ? 'JMD' : undefined,
        },
      },
    ];
  }

  if (widget.type === 'data_table') {
    return [
      {
        id: widget.widget_id,
        type: 'table',
        title: titleFromWidget(widget),
        w: 12,
        h: 4,
        data: rowsFromWidget(widget),
        source: sourceFromWidget(widget, metricKeysFromWidget(widget, 'date')),
        options: { columns: columnsFromWidget(widget) },
      },
    ];
  }

  return [blockedNote({ ...widget, error: `Unsupported governed widget type: ${widget.type}` })];
}

export const reportLayoutId = (reportId: string): string => `report-${reportId}`;

export function mergeGovernedWidgets(...groups: DashboardWidget[][]): DashboardWidget[] {
  const bySignature = new Set<string>();
  const byId = new Set<string>();
  const merged: DashboardWidget[] = [];
  for (const group of groups) {
    for (const widget of group) {
      const signature = widgetSourceSignature(widget);
      if (byId.has(widget.id) || (signature && bySignature.has(signature))) {
        continue;
      }
      byId.add(widget.id);
      if (signature) {
        bySignature.add(signature);
      }
      merged.push(widget);
    }
  }
  return merged;
}

export function reportingCatalogToWidgets(
  catalog: ReportingCatalogResponse,
  availability: ReportDataAvailabilityResponse | null,
): DashboardWidget[] {
  return catalog.metrics
    .filter((metric) => metric.widgets.includes('kpi'))
    .filter(
      (metric) => availability?.datasets[availabilityDatasetForMetric(metric.dataset, metric.key)],
    )
    .map((metric): DashboardWidget => {
      const runtime = availabilityFromMetric(metric, availability);
      return {
        id: `catalog-${metric.dataset}-${metric.key}-kpi`,
        type: 'kpi',
        title: labelFromKey(metric.key),
        x: 1,
        y: 1,
        w: 3,
        h: 2,
        data: null,
        source: {
          dataset: metric.dataset,
          widgetId: `catalog:${metric.dataset}:${metric.key}`,
          metrics: [metric.key],
          availability: metricAvailabilityForWidget(metric, availability),
        },
        options: {
          format: metricFormat(metric.key),
          currency: metricFormat(metric.key) === 'currency' ? 'JMD' : undefined,
          change: null,
          trend: runtime?.row_count ? [] : undefined,
        },
      };
    });
}

export function reportPreviewToLayout(preview: ReportPreviewResponse): DashboardLayoutConfig {
  let cursorY = 1;
  let kpiX = 1;
  const widgets: DashboardWidget[] = [];

  const flushKpiRow = () => {
    if (kpiX !== 1) {
      cursorY += 2;
      kpiX = 1;
    }
  };

  const place = (widget: Omit<DashboardWidget, 'x' | 'y'>) => {
    if (widget.type === 'kpi') {
      if (kpiX > DEFAULT_GRID_COLS - 2) {
        flushKpiRow();
      }
      widgets.push({ ...widget, x: kpiX, y: cursorY });
      kpiX += 3;
      if (kpiX > DEFAULT_GRID_COLS) {
        flushKpiRow();
      }
      return;
    }
    flushKpiRow();
    widgets.push({ ...widget, x: 1, y: cursorY });
    cursorY += widget.h;
  };

  for (const page of preview.pages) {
    for (const section of page.sections) {
      for (const widget of section.widgets) {
        widgetsFromPreviewWidget(widget).forEach(place);
      }
    }
  }

  flushKpiRow();

  return {
    id: reportLayoutId(preview.report.id),
    title: `${preview.report.name} layout`,
    cols: DEFAULT_GRID_COLS,
    rowHeight: DEFAULT_ROW_HEIGHT,
    widgets:
      widgets.length > 0
        ? widgets
        : [
            {
              id: 'empty-report-note',
              type: 'note',
              title: 'No renderable widgets',
              x: 1,
              y: 1,
              w: 12,
              h: 2,
              options: {
                text: 'The governed report preview returned no renderable widgets for this range.',
              },
            },
          ],
  };
}
