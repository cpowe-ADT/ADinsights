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
    formatter: (value, name) => [formatter(value), name ?? ''],
    labelFormatter: labelFormatter ?? ((value) => toDateLabel(value)),
    contentStyle,
    itemStyle: { color: chartTheme.tooltip.color, paddingBottom: 4 },
    labelStyle: { color: chartTheme.tooltip.labelColor, fontWeight: 600, marginBottom: 8 },
    cursor: { stroke: 'rgba(148, 163, 184, 0.35)', strokeDasharray: '3 3' },
    wrapperStyle: { outline: 'none' },
  };
};

export const axisTickFormatter = (value: ValueType) => formatCompactNumber(value);
