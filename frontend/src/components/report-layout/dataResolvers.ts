/**
 * Live-data binding for the config-driven layout. A widget's `dataKey` selects a
 * slice of the live dashboard store; the resolver returns the shape its widget
 * type expects. This is what turns a static config into a live report without
 * changing the schema — {@link GridCanvas}/{@link LayoutEditor} just call it.
 */
import type { DashboardWidget } from './layoutSchema';

/** The slice of live store state the resolver reads. */
export interface ResolverData {
  /** Campaign summary KPIs (spend, clicks, conversions, averageRoas, …). */
  summary?: Record<string, unknown> | null;
  /** Per-parish rows ({ parish, spend, clicks, roas, … }). */
  parish?: ReadonlyArray<Record<string, unknown>> | null;
}

/**
 * Resolve a widget's data from live store data via its `dataKey`:
 * - `summary.<field>` → number (kpi / gauge)
 * - `parish.<metric>` → `[{ label, value }]` (bar / pie)
 * - `parish.rows`     → the raw rows (table)
 * Falls back to the widget's inline `data` when there's no `dataKey` or no match.
 */
export function resolveStoreData(widget: DashboardWidget, data: ResolverData): unknown {
  const key = widget.dataKey;
  if (!key) return widget.data;

  if (key.startsWith('summary.')) {
    const value = data.summary?.[key.slice('summary.'.length)];
    return typeof value === 'number' ? value : null;
  }

  if (key.startsWith('parish.')) {
    const metric = key.slice('parish.'.length);
    const rows = data.parish ?? [];
    if (metric === 'rows') return rows;
    return rows.map((row) => ({
      label: String(row.parish ?? ''),
      value: Number(row[metric] ?? 0),
    }));
  }

  return widget.data;
}

/** Bind the resolver to a data snapshot — produces the `resolveData` callback. */
export function createStoreResolver(data: ResolverData) {
  return (widget: DashboardWidget): unknown => resolveStoreData(widget, data);
}
