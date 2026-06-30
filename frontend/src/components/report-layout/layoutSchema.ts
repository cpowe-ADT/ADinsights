/**
 * Config-driven report layout schema.
 *
 * A report/dashboard is data: an array of positioned widgets that the
 * {@link GridCanvas} renders from the shared viz kit. This is the substrate a
 * drag-and-drop editor edits later — the editor mutates this config, the canvas
 * renders it. Keep this file framework-agnostic (no React) so it can be shared
 * with serialization, validation, and the future editor.
 */
import type { KpiFormat } from '../viz';

/** Widget kinds the renderer can draw. */
export type WidgetType = 'kpi' | 'bar' | 'line' | 'pie' | 'gauge' | 'table' | 'note';

export interface LineSeries {
  key: string;
  label: string;
  color?: string;
  dashed?: boolean;
}

export interface TableColumn {
  /** Key into each row object. */
  key: string;
  header: string;
  align?: 'left' | 'right';
}

export interface WidgetOptions {
  /** kpi: value format */
  format?: KpiFormat;
  /** ISO currency for currency-formatted values */
  currency?: string;
  /** kpi: percent change vs prior period as a decimal (0.12 = +12%) */
  change?: number | null;
  /** kpi: sparkline points */
  trend?: number[];
  /** gauge: domain max (default 1.2) */
  max?: number;
  /** gauge: unit suffix on the center label */
  unit?: string;
  /** pie: center label text */
  centerLabel?: string;
  /** chart height in px */
  height?: number;
  /** line: series definitions keyed into each data row */
  series?: LineSeries[];
  /** line: axis/tooltip value format */
  yFormat?: 'number' | 'currency' | 'percent';
  /** table: column definitions */
  columns?: TableColumn[];
  /** note: plain text */
  text?: string;
}

export type WidgetMetricAvailabilityState =
  | 'available'
  | 'callable_no_data'
  | 'permission_gated'
  | 'unsupported';

export interface WidgetMetricAvailability {
  key: string;
  state: WidgetMetricAvailabilityState;
  note?: string;
  rowCount?: number;
}

export interface WidgetSourceBinding {
  dataset?: string;
  widgetId?: string;
  metrics?: string[];
  availability?: WidgetMetricAvailability[];
}

/** Grid placement: 1-based column/row start, span in grid units. */
export interface WidgetPlacement {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface DashboardWidget extends WidgetPlacement {
  id: string;
  type: WidgetType;
  title?: string;
  /** Key used by a data resolver to bind live data (see GridCanvas.resolveData). */
  dataKey?: string;
  /** Inline data; used when no resolver supplies data for this widget. */
  data?: unknown;
  options?: WidgetOptions;
  /** Optional governed report source metadata used by the builder UI. */
  source?: WidgetSourceBinding;
}

export interface DashboardLayoutConfig {
  id: string;
  title: string;
  /** Number of grid columns. */
  cols: number;
  /** Pixel height of one grid row unit. */
  rowHeight: number;
  widgets: DashboardWidget[];
}

export const DEFAULT_GRID_COLS = 12;
export const DEFAULT_ROW_HEIGHT = 64;

/**
 * Stable identity for governed report widgets across saved-layout edits. Widget
 * ids can change when a layout is imported or customized, but source-bound
 * widgets should still rebind to the current governed preview when dataset,
 * metric set, and renderer type match.
 */
export function widgetSourceSignature(widget: DashboardWidget): string | null {
  const source = widget.source;
  if (!source) return null;
  const dataset = source.dataset ?? '';
  const metrics = [...(source.metrics ?? [])].filter(Boolean).sort();
  if (metrics.length > 0) {
    return `${widget.type}|${dataset}|metrics:${metrics.join(',')}`;
  }
  if (source.widgetId) {
    return `${widget.type}|${dataset}|widget:${source.widgetId}`;
  }
  return null;
}

/** Lightweight structural validation — useful for the editor and saved configs. */
export function isDashboardLayoutConfig(value: unknown): value is DashboardLayoutConfig {
  if (!value || typeof value !== 'object') return false;
  const layout = value as Partial<DashboardLayoutConfig>;
  return (
    typeof layout.id === 'string' &&
    typeof layout.title === 'string' &&
    Array.isArray(layout.widgets) &&
    layout.widgets.every(
      (w) =>
        w &&
        typeof w.id === 'string' &&
        typeof w.type === 'string' &&
        typeof w.x === 'number' &&
        typeof w.y === 'number' &&
        typeof w.w === 'number' &&
        typeof w.h === 'number',
    )
  );
}
