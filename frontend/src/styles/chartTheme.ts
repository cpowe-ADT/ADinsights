import type { CSSProperties } from 'react';
import type { TooltipProps } from 'recharts';
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent';

import { formatCompactNumber, formatCurrency, formatPercent } from '../lib/formatNumber';

export const chartPalette = ['#2563eb', '#f97316', '#0ea5e9', '#10b981', '#9333ea', '#f43f5e'];

export const chartTheme = {
  grid: {
    stroke: 'rgba(15, 23, 42, 0.12)',
    strokeDasharray: '4 6',
  },
  tooltip: {
    backgroundColor: '#0f172a',
    color: '#f8fafc',
    borderRadius: 8,
    borderColor: 'rgba(148, 163, 184, 0.35)',
    labelColor: '#cbd5f5',
  },
  point: {
    radius: 4,
    activeRadius: 6,
  },
  cornerRadius: 8,
} as const;

export const chartMargins = { top: 16, right: 24, bottom: 16, left: 8 } as const;

export type ChartValueType = 'number' | 'currency' | 'percent';

export interface TooltipConfig {
  valueType?: ChartValueType;
  currency?: string;
  labelFormatter?: TooltipProps<ValueType, NameType>['labelFormatter'];
  valueFormatter?: (value: ValueType) => string;
}

const toDateLabel = (value: ValueType): string => {
  if (value instanceof Date) {
    return new Intl.DateTimeFormat('en-JM', { month: 'short', day: 'numeric' }).format(value);
  }

  const parsed = new Date(`${value}`);
  if (!Number.isNaN(parsed.getTime())) {
    return new Intl.DateTimeFormat('en-JM', { month: 'short', day: 'numeric' }).format(parsed);
  }

  return `${value}`;
};

const createValueFormatter = (
  valueType: ChartValueType,
  currency: string,
  override?: (value: ValueType) => string,
) => {
  if (override) {
    return override;
  }

  switch (valueType) {
    case 'currency':
      return (value: ValueType) => formatCurrency(value, currency);
    case 'percent':
      return (value: ValueType) => formatPercent(value);
    default:
      return (value: ValueType) => formatCompactNumber(value);
  }
};

export const createTooltipProps = ({
  valueType = 'number',
  currency = 'JMD',
  labelFormatter,
  valueFormatter,
}: TooltipConfig = {}): Partial<TooltipProps<ValueType, NameType>> => {
  const formatter = createValueFormatter(valueType, currency, valueFormatter);

  const contentStyle: CSSProperties = {
    backgroundColor: chartTheme.tooltip.backgroundColor,
    color: chartTheme.tooltip.color,
    borderRadius: chartTheme.tooltip.borderRadius,
    borderColor: chartTheme.tooltip.borderColor,
    boxShadow: '0 18px 36px rgba(15, 23, 42, 0.2)',
    padding: '0.75rem 1rem',
  };

  return {
    formatter: (value, name) => [value !== undefined ? formatter(value) : '', name ?? ''],
    labelFormatter: labelFormatter ?? ((value) => toDateLabel(value)),
    contentStyle,
    itemStyle: { color: chartTheme.tooltip.color, paddingBottom: 4 },
    labelStyle: { color: chartTheme.tooltip.labelColor, fontWeight: 600, marginBottom: 8 },
    cursor: { stroke: 'rgba(148, 163, 184, 0.35)', strokeDasharray: '3 3' },
    wrapperStyle: { outline: 'none' },
  };
};

export const axisTickFormatter = (value: ValueType | undefined) =>
  value !== undefined ? formatCompactNumber(value) : '';

/**
 * CSS variable names for the viz kit. Primitives under
 * `components/viz/` should prefer these CSS custom properties on
 * Recharts SVG attributes (`stroke="var(--viz-series-0)"`) so that
 * theme switches cascade correctly. Fall back to literal hex from
 * `chartPalette` only inside `<defs>` blocks where the cascade may
 * not resolve in time (e.g. gradient stops).
 */
export const VIZ_CSS_VARS = {
  seriesPalette: [
    '--viz-series-0',
    '--viz-series-1',
    '--viz-series-2',
    '--viz-series-3',
    '--viz-series-4',
    '--viz-series-5',
  ] as const,
  axisLine: '--viz-axis-line',
  axisTick: '--viz-axis-tick',
  grid: '--viz-grid',
  gridStrong: '--viz-grid-strong',
  peerAvg: '--viz-platform-peer-avg',
  pointFocus: '--viz-point-focus',
  tooltipSurface: '--viz-tooltip-surface',
  tooltipText: '--viz-tooltip-text',
  legendText: '--viz-legend-text',
} as const;

/**
 * Semantic platform-specific chart colors. Uses literal hex from
 * `chartPalette` for backward compatibility with domain wrappers that
 * already rely on these values. New viz primitives should prefer the
 * `var(--viz-platform-*)` tokens so the dark theme cascade applies.
 */
export const PLATFORM_CHART_TOKENS = {
  meta_ads: chartPalette[0],
  google_ads: chartPalette[1],
  peer_avg: 'rgba(148, 163, 184, 0.55)',
} as const;

/**
 * Campaign status colors. Matches `--viz-status-*` tokens but exposed
 * as literal hex for use in Recharts `<Cell>` fills where the CSS
 * cascade does not resolve (inline SVG attributes in <defs>).
 */
export const STATUS_COLORS = {
  ENABLED: chartPalette[3],
  PAUSED: '#b45309',
  REMOVED: chartPalette[5],
} as const;

/**
 * Round-robin palette lookup for unspecified series colors. Pass the
 * series index; returns a stable hex from `chartPalette`.
 */
export function resolveSeriesColor(index: number): string {
  if (!Number.isFinite(index) || index < 0) {
    return chartPalette[0];
  }
  return chartPalette[index % chartPalette.length];
}
