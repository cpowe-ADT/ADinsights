import { useMemo } from 'react';
import type { ComponentType } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
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
import VizEmptyIcon from './VizEmptyIcon';

export interface DistributionBarDatum {
  label: string;
  value: number;
  color?: string;
  /** Optional pattern id for secondary (non-color) encoding. */
  patternId?: string;
}

export interface DistributionBarProps {
  data: DistributionBarDatum[];
  /** Horizontal (default) renders categories on the Y axis. */
  orientation?: 'horizontal' | 'vertical';
  /** When true, bars are annotated with their share of the total. */
  showPercent?: boolean;
  /** Value formatting for tooltip and axis. */
  yFormat?: ChartValueType;
  /** ISO currency code. */
  currency?: string;
  /** Reason code forwarded to <EmptyState>. */
  emptyReasonCode?: string;
  /** Render a shimmer placeholder instead of the chart. */
  isLoading?: boolean;
  /** Chart height. */
  height?: number;
  /** Required accessible label. */
  ariaLabel: string;
}

const axisTickStyle = { fill: 'var(--viz-axis-tick)', fontSize: 12 } as const;

const formatValue = (value: number, format: ChartValueType, currency: string): string => {
  if (format === 'currency') return formatCurrency(value, currency);
  if (format === 'percent') return formatPercent(value);
  return formatCompactNumber(value);
};

/**
 * DistributionBar — single-series category distribution (horizontal by
 * default). Use this primitive when you need to compare a value across
 * categorical labels (e.g. parish, age bucket, campaign name). For
 * stacked or grouped bars, use a domain wrapper that composes multiple
 * Recharts `<Bar>` elements.
 */
const DistributionBar = ({
  data,
  orientation = 'horizontal',
  showPercent = false,
  yFormat = 'number',
  currency = 'JMD',
  emptyReasonCode = 'no_data_for_range',
  isLoading = false,
  height = 280,
  ariaLabel,
}: DistributionBarProps) => {
  const total = useMemo(() => data.reduce((acc, d) => acc + (Number(d.value) || 0), 0), [data]);

  const chartData = useMemo(
    () =>
      data.map((d, i) => ({
        label: d.label,
        value: d.value,
        color: d.color ?? resolveSeriesColor(i),
        percent: total > 0 ? (d.value / total) * 100 : 0,
      })),
    [data, total],
  );

  const tooltipProps = useMemo(
    () => createTooltipProps({ valueType: yFormat, currency }),
    [yFormat, currency],
  );

  const BarComponent = Bar as unknown as ComponentType<Record<string, unknown>>;
  const GridComponent = CartesianGrid as unknown as ComponentType<Record<string, unknown>>;
  const XAxisComponent = XAxis as unknown as ComponentType<Record<string, unknown>>;
  const YAxisComponent = YAxis as unknown as ComponentType<Record<string, unknown>>;
  const TooltipComponent = Tooltip as unknown as ComponentType<Record<string, unknown>>;
  const LabelListComponent = LabelList as unknown as ComponentType<Record<string, unknown>>;

  if (isLoading) {
    return <ChartSkeleton variant="bar" height={height} />;
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

  const isHorizontal = orientation === 'horizontal';
  const layout: 'horizontal' | 'vertical' = isHorizontal ? 'vertical' : 'horizontal';
  // Note: Recharts `layout="vertical"` means categories on the Y axis,
  // which is what we call "horizontal bars" in product terms.

  const categoryAxisProps = {
    dataKey: 'label',
    axisLine: false,
    tickLine: false,
    tick: axisTickStyle,
  };
  const valueAxisProps = {
    axisLine: false,
    tickLine: false,
    tick: axisTickStyle,
    tickFormatter: (value: number) => axisTickFormatter(value),
  };

  return (
    <div style={{ width: '100%' }}>
      <div role="img" aria-label={ariaLabel} style={{ width: '100%' }}>
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={chartData} layout={layout} margin={chartMargins}>
            <defs>
              {/* Default pattern fill used when a datum opts into non-color encoding. */}
              <pattern
                id="viz-pattern-diagonal"
                patternUnits="userSpaceOnUse"
                width="6"
                height="6"
                patternTransform="rotate(45)"
              >
                <line
                  x1="0"
                  y="0"
                  x2="0"
                  y2="6"
                  stroke="currentColor"
                  strokeWidth="2"
                  opacity="var(--viz-pattern-opacity)"
                />
              </pattern>
            </defs>
            <GridComponent
              stroke="var(--viz-grid)"
              strokeDasharray={chartTheme.grid.strokeDasharray}
              vertical={!isHorizontal}
              horizontal={isHorizontal}
            />
            {isHorizontal ? (
              <>
                <XAxisComponent type="number" {...valueAxisProps} />
                <YAxisComponent type="category" width={96} {...categoryAxisProps} />
              </>
            ) : (
              <>
                <XAxisComponent type="category" {...categoryAxisProps} />
                <YAxisComponent type="number" width={68} {...valueAxisProps} />
              </>
            )}
            <TooltipComponent {...tooltipProps} />
            <BarComponent
              dataKey="value"
              radius={[chartTheme.cornerRadius / 2, chartTheme.cornerRadius / 2, 0, 0]}
            >
              {chartData.map((entry, i) => {
                const datum = data[i];
                const patternFill = datum?.patternId ? `url(#${datum.patternId})` : entry.color;
                return <Cell key={entry.label} fill={patternFill} />;
              })}
              {showPercent ? (
                <LabelListComponent
                  dataKey="percent"
                  position={isHorizontal ? 'right' : 'top'}
                  formatter={(value: number) => `${value.toFixed(0)}%`}
                  style={{ fill: 'var(--viz-axis-tick)', fontSize: 12 }}
                />
              ) : null}
            </BarComponent>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only" aria-label={ariaLabel}>
        <caption>{ariaLabel}</caption>
        <thead>
          <tr>
            <th scope="col">Category</th>
            <th scope="col">Value</th>
            {showPercent ? <th scope="col">Share</th> : null}
          </tr>
        </thead>
        <tbody>
          {chartData.map((row) => (
            <tr key={row.label}>
              <th scope="row">{row.label}</th>
              <td>{formatValue(row.value, yFormat, currency)}</td>
              {showPercent ? <td>{row.percent.toFixed(1)}%</td> : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default DistributionBar;
