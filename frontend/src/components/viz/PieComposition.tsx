import { useMemo } from 'react';
import type { ComponentType } from 'react';
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import {
  createTooltipProps,
  resolveSeriesColor,
  type ChartValueType,
} from '../../styles/chartTheme';
import { formatCompactNumber, formatCurrency, formatPercent } from '../../lib/formatNumber';
import EmptyState from '../EmptyState';

import ChartSkeleton from './ChartSkeleton';
import VizEmptyIcon from './VizEmptyIcon';

export interface PieCompositionDatum {
  label: string;
  value: number;
  color?: string;
  patternId?: string;
}

export interface PieCompositionProps {
  data: PieCompositionDatum[];
  /** Default 60 for donut; pass 0 to render a pie. */
  innerRadius?: number;
  /** Value format used in tooltip. */
  yFormat?: ChartValueType;
  /** ISO currency code. */
  currency?: string;
  /** Render legend (default true). */
  showLegend?: boolean;
  /** Text rendered at donut center (e.g. total). */
  centerLabel?: string;
  /** Reason code forwarded to <EmptyState>. */
  emptyReasonCode?: string;
  /** Render a shimmer placeholder. */
  isLoading?: boolean;
  /** Chart height. */
  height?: number;
  /** Required accessible label. */
  ariaLabel: string;
}

const formatValue = (value: number, format: ChartValueType, currency: string): string => {
  if (format === 'currency') return formatCurrency(value, currency);
  if (format === 'percent') return formatPercent(value);
  return formatCompactNumber(value);
};

/**
 * PieComposition — donut (default) or pie chart for part-to-whole
 * breakdowns. Each segment receives a color + optional cross-hatch
 * pattern so color alone is not the encoding (WCAG requirement).
 */
const PieComposition = ({
  data,
  innerRadius = 60,
  yFormat = 'number',
  currency = 'JMD',
  showLegend = true,
  centerLabel,
  emptyReasonCode = 'no_data_for_range',
  isLoading = false,
  height = 260,
  ariaLabel,
}: PieCompositionProps) => {
  const total = useMemo(() => data.reduce((acc, d) => acc + (Number(d.value) || 0), 0), [data]);

  const chartData = useMemo(
    () =>
      data.map((d, i) => ({
        name: d.label,
        value: d.value,
        color: d.color ?? resolveSeriesColor(i),
        patternId: d.patternId,
        percent: total > 0 ? (d.value / total) * 100 : 0,
      })),
    [data, total],
  );

  const tooltipProps = useMemo(
    () => createTooltipProps({ valueType: yFormat, currency }),
    [yFormat, currency],
  );

  const PieComponent = Pie as unknown as ComponentType<Record<string, unknown>>;
  const TooltipComponent = Tooltip as unknown as ComponentType<Record<string, unknown>>;
  const LegendComponent = Legend as unknown as ComponentType<Record<string, unknown>>;

  if (isLoading) {
    return <ChartSkeleton variant="pie" height={height} />;
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

  const outerRadius = Math.max(innerRadius + 20, Math.min(height / 2 - 20, 110));

  return (
    <div style={{ width: '100%' }}>
      <div role="img" aria-label={ariaLabel} style={{ width: '100%', position: 'relative' }}>
        <ResponsiveContainer width="100%" height={height}>
          <PieChart>
            <defs>
              <pattern
                id="viz-pie-pattern-dots"
                patternUnits="userSpaceOnUse"
                width="6"
                height="6"
              >
                <circle cx="3" cy="3" r="1.2" fill="currentColor" opacity="var(--viz-pattern-opacity)" />
              </pattern>
            </defs>
            <PieComponent
              data={chartData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={innerRadius}
              outerRadius={outerRadius}
              paddingAngle={innerRadius > 0 ? 2 : 0}
              stroke="var(--color-surface-card)"
            >
              {chartData.map((entry) => {
                const fill = entry.patternId ? `url(#${entry.patternId})` : entry.color;
                return <Cell key={entry.name} fill={fill} />;
              })}
            </PieComponent>
            <TooltipComponent {...tooltipProps} />
            {showLegend ? (
              <LegendComponent wrapperStyle={{ color: 'var(--viz-legend-text)' }} />
            ) : null}
          </PieChart>
        </ResponsiveContainer>
        {centerLabel && innerRadius > 0 ? (
          <div
            aria-hidden="true"
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              pointerEvents: 'none',
              color: 'var(--color-text-primary)',
              fontWeight: 600,
              fontSize: 16,
            }}
          >
            {centerLabel}
          </div>
        ) : null}
      </div>
      <table className="sr-only" aria-label={ariaLabel}>
        <caption>{ariaLabel}</caption>
        <thead>
          <tr>
            <th scope="col">Label</th>
            <th scope="col">Value</th>
            <th scope="col">Share</th>
          </tr>
        </thead>
        <tbody>
          {chartData.map((row) => (
            <tr key={row.name}>
              <th scope="row">{row.name}</th>
              <td>{formatValue(row.value, yFormat, currency)}</td>
              <td>{row.percent.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default PieComposition;
