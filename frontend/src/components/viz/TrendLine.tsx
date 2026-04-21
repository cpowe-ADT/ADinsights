import { useMemo } from 'react';
import type { ComponentType } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import {
  axisTickFormatter,
  chartMargins,
  chartTheme,
  createTooltipProps,
  resolveSeriesColor,
  type ChartValueType,
} from '../../styles/chartTheme';
import { formatCompactNumber, formatCurrency, formatPercent } from '../../lib/formatNumber';
import EmptyState from '../EmptyState';

import ChartSkeleton from './ChartSkeleton';
import PeerAvgLine from './PeerAvgLine';
import VizEmptyIcon from './VizEmptyIcon';

export interface TrendLineSeries {
  /** Key inside each data row. */
  key: string;
  /** Human-readable legend/tooltip label. */
  label: string;
  /** Override stroke; defaults to the palette position of the series. */
  color?: string;
  /** Render the series with a dashed stroke (secondary encoding). */
  dashed?: boolean;
  /** Bind to left (default) or right y-axis. */
  yAxis?: 'left' | 'right';
}

export interface TrendLinePoint {
  date: string;
  [key: string]: string | number | null | undefined;
}

export interface TrendLinePeerPoint {
  date: string;
  value: number;
}

export interface TrendLineProps {
  /** Rows keyed on `date` plus one numeric entry per series key. */
  data: TrendLinePoint[];
  /** Series definitions controlling stroke, label, and axis binding. */
  series: TrendLineSeries[];
  /** Optional peer-average series rendered as a dashed secondary line. */
  peerData?: TrendLinePeerPoint[];
  /** Value type for the left Y axis / primary tooltips. */
  yFormat?: ChartValueType;
  /** Value type for the right Y axis when any series opts into it. */
  rightYFormat?: ChartValueType;
  /** ISO currency code passed to currency formatter. */
  currency?: string;
  /** Fixed chart footprint. */
  height?: number;
  /** Reason code forwarded to <EmptyState> when `data` is empty. */
  emptyReasonCode?: string;
  /** Render a shimmer placeholder instead of the chart. */
  isLoading?: boolean;
  /** Required accessible label describing the chart. */
  ariaLabel: string;
  /** Optional click handler fired with the clicked row's `date`. */
  onPointClick?: (date: string) => void;
}

const axisTickStyle = { fill: 'var(--viz-axis-tick)', fontSize: 12 } as const;

const formatValueForTable = (
  value: number | null | undefined,
  format: ChartValueType,
  currency: string,
): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  if (format === 'currency') return formatCurrency(value, currency);
  if (format === 'percent') return formatPercent(value);
  return formatCompactNumber(value);
};

/**
 * TrendLine — multi-series line chart primitive.
 *
 * Renders an SVG `<LineChart>` wrapped in `role="img" aria-label`, plus
 * a visually hidden `<table>` carrying the same values for screen
 * readers. The S1b `<AccessibleTableToggle>` composes this primitive
 * when a visible table toggle is required.
 */
const TrendLine = ({
  data,
  series,
  peerData,
  yFormat = 'number',
  rightYFormat,
  currency = 'JMD',
  height = 260,
  emptyReasonCode = 'no_data_for_range',
  isLoading = false,
  ariaLabel,
  onPointClick,
}: TrendLineProps) => {
  const mergedData = useMemo<TrendLinePoint[]>(() => {
    if (!peerData || peerData.length === 0) return data;
    const peerByDate = new Map(peerData.map((p) => [p.date, p.value]));
    return data.map((row) => ({
      ...row,
      __peerAvg: peerByDate.get(row.date) ?? null,
    }));
  }, [data, peerData]);

  const tooltipProps = useMemo(
    () => createTooltipProps({ valueType: yFormat, currency }),
    [yFormat, currency],
  );

  const GridComponent = CartesianGrid as unknown as ComponentType<Record<string, unknown>>;
  const XAxisComponent = XAxis as unknown as ComponentType<Record<string, unknown>>;
  const YAxisComponent = YAxis as unknown as ComponentType<Record<string, unknown>>;
  const TooltipComponent = Tooltip as unknown as ComponentType<Record<string, unknown>>;
  const LineComponent = Line as unknown as ComponentType<Record<string, unknown>>;
  const LegendComponent = Legend as unknown as ComponentType<Record<string, unknown>>;

  if (isLoading) {
    return <ChartSkeleton variant="line" height={height} />;
  }

  if (!data || data.length === 0) {
    return (
      <EmptyState
        icon={<VizEmptyIcon />}
        title="No data to display"
        message="There is no data for the selected range."
        reasonCode={emptyReasonCode}
      />
    );
  }

  const hasRightAxis = series.some((s) => s.yAxis === 'right');
  const showLegend = series.length > 1 || Boolean(peerData && peerData.length > 0);

  const handleClick = onPointClick
    ? (payload: unknown) => {
        const event = payload as { activeLabel?: string | number };
        if (event?.activeLabel !== undefined) {
          onPointClick(String(event.activeLabel));
        }
      }
    : undefined;

  return (
    <div style={{ width: '100%' }}>
      <div role="img" aria-label={ariaLabel} style={{ width: '100%' }}>
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={mergedData} margin={chartMargins} onClick={handleClick}>
            <GridComponent
              stroke="var(--viz-grid)"
              strokeDasharray={chartTheme.grid.strokeDasharray}
              vertical={false}
            />
            <XAxisComponent
              dataKey="date"
              axisLine={false}
              tickLine={false}
              tickMargin={12}
              tick={axisTickStyle}
            />
            <YAxisComponent
              yAxisId="left"
              axisLine={false}
              tickLine={false}
              tick={axisTickStyle}
              width={68}
              tickFormatter={(value: number) => axisTickFormatter(value)}
            />
            {hasRightAxis ? (
              <YAxisComponent
                yAxisId="right"
                orientation="right"
                axisLine={false}
                tickLine={false}
                tick={axisTickStyle}
                width={68}
                tickFormatter={(value: number) => axisTickFormatter(value)}
              />
            ) : null}
            <TooltipComponent {...tooltipProps} />
            {showLegend ? (
              <LegendComponent
                wrapperStyle={{ paddingTop: 12, color: 'var(--viz-legend-text)' }}
              />
            ) : null}
            {series.map((s, i) => (
              <LineComponent
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color ?? resolveSeriesColor(i)}
                strokeDasharray={s.dashed ? '6 4' : undefined}
                strokeWidth={2}
                dot={{ r: chartTheme.point.radius }}
                activeDot={{ r: chartTheme.point.activeRadius }}
                yAxisId={s.yAxis ?? 'left'}
              />
            ))}
            {peerData && peerData.length > 0 ? <PeerAvgLine data={peerData} yAxisId="left" /> : null}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {/* Accessible equivalent for screen readers. */}
      <table className="sr-only" aria-label={ariaLabel}>
        <caption>{ariaLabel}</caption>
        <thead>
          <tr>
            <th scope="col">Date</th>
            {series.map((s) => (
              <th key={s.key} scope="col">
                {s.label}
              </th>
            ))}
            {peerData && peerData.length > 0 ? <th scope="col">Peer avg</th> : null}
          </tr>
        </thead>
        <tbody>
          {mergedData.map((row) => (
            <tr key={String(row.date)}>
              <th scope="row">{String(row.date)}</th>
              {series.map((s) => {
                const raw = row[s.key];
                const numeric =
                  typeof raw === 'number'
                    ? raw
                    : raw === null || raw === undefined
                      ? null
                      : Number(raw);
                const format = s.yAxis === 'right' ? (rightYFormat ?? yFormat) : yFormat;
                return <td key={s.key}>{formatValueForTable(numeric, format, currency)}</td>;
              })}
              {peerData && peerData.length > 0 ? (
                <td>
                  {formatValueForTable(
                    typeof row['__peerAvg'] === 'number' ? (row['__peerAvg'] as number) : null,
                    yFormat,
                    currency,
                  )}
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default TrendLine;
