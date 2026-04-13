import { useMemo } from 'react';
import type { ComponentType } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { normalizeParishValue } from '../state/useDashboardStore';
import type { ParishAggregate } from '../state/useDashboardStore';
import {
  chartMargins,
  chartPalette,
  chartTheme,
  createTooltipProps,
} from '../styles/chartTheme';
import { formatCurrency, formatNumber, formatRatio } from '../lib/format';

type MetricKey = 'spend' | 'impressions' | 'clicks' | 'conversions' | 'roas';

interface ParishComparisonChartProps {
  data: ParishAggregate[];
  metric: string;
  currency: string;
  selectedParish?: string;
}

const METRIC_LABELS: Record<MetricKey, string> = {
  spend: 'Spend',
  impressions: 'Impressions',
  clicks: 'Clicks',
  conversions: 'Conversions',
  roas: 'ROAS',
};

const BAR_HEIGHT = 32;
const BAR_GAP = 4;
const CHART_PADDING = 48;

const ParishComparisonChart = ({
  data,
  metric,
  currency,
  selectedParish,
}: ParishComparisonChartProps) => {
  const metricKey = (
    Object.keys(METRIC_LABELS).includes(metric) ? metric : 'spend'
  ) as MetricKey;

  const chartData = useMemo(
    () =>
      [...data]
        .map((row) => ({
          parish: row.parish,
          value: Number(row[metricKey] ?? 0),
        }))
        .sort((a, b) => b.value - a.value),
    [data, metricKey],
  );

  const chartHeight = chartData.length * (BAR_HEIGHT + BAR_GAP) + CHART_PADDING;

  const tooltipProps = useMemo(() => {
    if (metricKey === 'spend') {
      return createTooltipProps({ valueType: 'currency', currency });
    }
    if (metricKey === 'roas') {
      return createTooltipProps({
        valueType: 'number',
        valueFormatter: (v) => formatRatio(Number(v), 2),
      });
    }
    return createTooltipProps({ valueType: 'number' });
  }, [metricKey, currency]);

  // Recharts type casts for strict JSX
  const BarComponent = Bar as unknown as ComponentType<Record<string, unknown>>;
  const GridComponent = CartesianGrid as unknown as ComponentType<Record<string, unknown>>;
  const XAxisComponent = XAxis as unknown as ComponentType<Record<string, unknown>>;
  const YAxisComponent = YAxis as unknown as ComponentType<Record<string, unknown>>;
  const TooltipComponent = Tooltip as unknown as ComponentType<Record<string, unknown>>;

  const primaryColor = chartPalette[0];
  const dimmedColor = `${primaryColor}66`;

  return (
    <ResponsiveContainer width="100%" height={chartHeight}>
      <BarChart data={chartData} layout="vertical" margin={{ ...chartMargins, left: 100 }}>
        <GridComponent
          horizontal={false}
          stroke={chartTheme.grid.stroke}
          strokeDasharray={chartTheme.grid.strokeDasharray}
        />
        <XAxisComponent
          type="number"
          tickFormatter={
            metricKey === 'spend'
              ? (v: number) => formatCurrency(v, currency, 0)
              : metricKey === 'roas'
                ? (v: number) => formatRatio(v, 1)
                : (v: number) => formatNumber(v)
          }
          tick={{ fill: 'var(--color-text-muted)', fontSize: 12 }}
        />
        <YAxisComponent
          type="category"
          dataKey="parish"
          width={96}
          tick={{ fill: 'var(--color-text-primary)', fontSize: 13 }}
        />
        <TooltipComponent {...tooltipProps} />
        <BarComponent
          dataKey="value"
          name={METRIC_LABELS[metricKey]}
          radius={[0, chartTheme.cornerRadius / 2, chartTheme.cornerRadius / 2, 0]}
          barSize={BAR_HEIGHT}
        >
          {chartData.map((entry) => (
            <Cell
              key={entry.parish}
              fill={
                !selectedParish || normalizeParishValue(entry.parish) === normalizeParishValue(selectedParish)
                  ? primaryColor
                  : dimmedColor
              }
            />
          ))}
        </BarComponent>
      </BarChart>
    </ResponsiveContainer>
  );
};

export default ParishComparisonChart;
