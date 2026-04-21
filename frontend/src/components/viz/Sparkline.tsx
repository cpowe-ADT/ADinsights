import type { ComponentType } from 'react';
import { Line, LineChart, ResponsiveContainer } from 'recharts';

import { resolveSeriesColor } from '../../styles/chartTheme';

import ChartSkeleton from './ChartSkeleton';

export interface SparklinePoint {
  date: string;
  value: number;
}

export interface SparklineProps {
  /** Ordered data points; x-axis is implicit. */
  data: SparklinePoint[];
  /** Stroke color. Defaults to series index 0. */
  color?: string;
  /** Fixed height (no axes). Default 40. */
  height?: number;
  /** Required accessible label — describes the metric being trended. */
  ariaLabel: string;
  /** Optional className applied to the wrapping div. */
  className?: string;
  /** Render a shimmer placeholder instead of the chart. */
  isLoading?: boolean;
}

/**
 * Sparkline — a tiny inline trend line with no axes, grid, legend, or
 * tooltip. Intended for table-cell usage where the adjacent cell
 * already carries the numeric value (the table IS the accessible
 * equivalent, so no `<AccessibleTableToggle>` wrapper).
 */
const Sparkline = ({
  data,
  color,
  height = 40,
  ariaLabel,
  className,
  isLoading = false,
}: SparklineProps) => {
  if (isLoading) {
    return <ChartSkeleton variant="sparkline" height={height} />;
  }

  if (!data || data.length === 0) {
    // Empty sparkline renders an empty focusable region rather than
    // collapsing; callers decide whether to render `--` instead.
    return (
      <div
        role="img"
        aria-label={`${ariaLabel}: no data`}
        style={{ height, width: '100%' }}
        className={className}
      />
    );
  }

  const LineComponent = Line as unknown as ComponentType<Record<string, unknown>>;
  const stroke = color ?? resolveSeriesColor(0);

  return (
    <div
      role="img"
      aria-label={ariaLabel}
      style={{ height, width: '100%' }}
      className={className}
    >
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <LineComponent
            type="monotone"
            dataKey="value"
            stroke={stroke}
            strokeWidth={2}
            dot={false}
            activeDot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default Sparkline;
