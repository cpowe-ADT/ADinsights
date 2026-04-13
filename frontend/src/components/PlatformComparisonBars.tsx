import { useMemo } from 'react';
import type { ComponentType } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { PlatformBreakdown } from '../state/useDashboardStore';
import { chartMargins, chartPalette, chartTheme, createTooltipProps } from '../styles/chartTheme';

const PLATFORM_COLORS: Record<string, string> = {
  facebook: chartPalette[0],
  instagram: chartPalette[1],
  audience_network: chartPalette[2],
  messenger: chartPalette[3],
};

const PLATFORM_LABELS: Record<string, string> = {
  facebook: 'Facebook',
  instagram: 'Instagram',
  audience_network: 'Audience Network',
  messenger: 'Messenger',
};

type MetricKey = 'spend' | 'impressions' | 'clicks' | 'conversions';

interface PlatformComparisonBarsProps {
  data: PlatformBreakdown[];
  metric?: MetricKey;
  currency?: string;
}

const PlatformComparisonBars = ({
  data,
  metric = 'spend',
  currency = 'USD',
}: PlatformComparisonBarsProps) => {
  const chartData = useMemo(
    () =>
      data.map((row) => ({
        name: PLATFORM_LABELS[row.platform] ?? row.platform,
        value: row[metric],
        fill: PLATFORM_COLORS[row.platform] ?? chartPalette[4],
      })),
    [data, metric],
  );

  const tooltipProps = useMemo(
    () =>
      metric === 'spend'
        ? createTooltipProps({ valueType: 'currency', currency })
        : createTooltipProps({ valueType: 'number' }),
    [metric, currency],
  );

  const BarComponent = Bar as unknown as ComponentType<Record<string, unknown>>;
  const GridComponent = CartesianGrid as unknown as ComponentType<Record<string, unknown>>;
  const XAxisComponent = XAxis as unknown as ComponentType<Record<string, unknown>>;
  const YAxisComponent = YAxis as unknown as ComponentType<Record<string, unknown>>;
  const TooltipComponent = Tooltip as unknown as ComponentType<Record<string, unknown>>;

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData} margin={chartMargins}>
        <GridComponent
          vertical={false}
          stroke={chartTheme.grid.stroke}
          strokeDasharray={chartTheme.grid.strokeDasharray}
        />
        <XAxisComponent
          dataKey="name"
          tick={{ fill: 'var(--color-text-primary)', fontSize: 13 }}
        />
        <YAxisComponent
          tick={{ fill: 'var(--color-text-muted)', fontSize: 12 }}
        />
        <TooltipComponent {...tooltipProps} />
        <BarComponent
          dataKey="value"
          radius={[chartTheme.cornerRadius / 2, chartTheme.cornerRadius / 2, 0, 0]}
        >
          {chartData.map((entry) => (
            <Cell key={entry.name} fill={entry.fill} />
          ))}
        </BarComponent>
      </BarChart>
    </ResponsiveContainer>
  );
};

export default PlatformComparisonBars;
