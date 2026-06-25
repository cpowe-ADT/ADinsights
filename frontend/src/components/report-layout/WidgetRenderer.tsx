import type { ReactElement } from 'react';
import type { ColumnDef } from '@tanstack/react-table';

import {
  DistributionBar,
  GaugeRing,
  KpiTile,
  PieComposition,
  VizDataTable,
} from '../viz';
import type { DashboardWidget } from './layoutSchema';

export interface WidgetRendererProps {
  widget: DashboardWidget;
  /** Resolved data; falls back to the widget's inline `data`. */
  data?: unknown;
}

type ChartDatum = { label: string; value: number; color?: string };
type TableRow = Record<string, unknown>;

const asChartData = (value: unknown): ChartDatum[] =>
  Array.isArray(value) ? (value as ChartDatum[]) : [];

/**
 * Maps a {@link DashboardWidget} to a shared viz-kit component. Pure and
 * data-driven so the same renderer serves the static report view today and the
 * drag-and-drop editor later. Unknown types degrade gracefully (never throw).
 */
const WidgetRenderer = ({ widget, data }: WidgetRendererProps): ReactElement => {
  const value = data ?? widget.data;
  const opts = widget.options ?? {};
  const title = widget.title ?? '';

  switch (widget.type) {
    case 'kpi':
      return (
        <KpiTile
          label={title}
          value={typeof value === 'number' ? value : null}
          format={opts.format}
          currency={opts.currency}
          change={opts.change ?? null}
          trend={opts.trend}
        />
      );
    case 'bar':
      return (
        <DistributionBar
          data={asChartData(value)}
          ariaLabel={title || 'Distribution'}
          currency={opts.currency}
          height={opts.height}
        />
      );
    case 'pie':
      return (
        <PieComposition
          data={asChartData(value)}
          ariaLabel={title || 'Composition'}
          centerLabel={opts.centerLabel}
          currency={opts.currency}
          height={opts.height}
        />
      );
    case 'gauge':
      return (
        <GaugeRing
          value={typeof value === 'number' ? value : NaN}
          label={title}
          ariaLabel={title || 'Gauge'}
          max={opts.max}
          unit={opts.unit}
        />
      );
    case 'table': {
      const rows = (Array.isArray(value) ? value : []) as TableRow[];
      const columns: ColumnDef<TableRow, unknown>[] = (opts.columns ?? []).map((col) => ({
        accessorKey: col.key,
        header: col.header,
      }));
      return (
        <VizDataTable<TableRow>
          columns={columns}
          data={rows}
          title={title || undefined}
          ariaLabel={title || 'Table'}
        />
      );
    }
    case 'note':
      return <p className="report-grid__note">{opts.text ?? ''}</p>;
    default:
      return (
        <div className="report-grid__note" role="note">
          Unsupported widget type
        </div>
      );
  }
};

export default WidgetRenderer;
