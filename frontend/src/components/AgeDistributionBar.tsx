import { useMemo } from 'react';
import type { ComponentType } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import type { AgeGenderBreakdown } from '../state/useDashboardStore';
import { chartMargins, chartPalette, chartTheme, createTooltipProps } from '../styles/chartTheme';

const AGE_ORDER = ['13-17', '18-24', '25-34', '35-44', '45-54', '55-64', '65+'];
const MALE_COLOR = chartPalette[0];
const FEMALE_COLOR = chartPalette[1];

type MetricKey = 'spend' | 'impressions' | 'clicks' | 'conversions';

interface AgeDistributionBarProps {
  data: AgeGenderBreakdown[];
  metric: MetricKey;
  currency?: string;
}

const AgeDistributionBar = ({ data, metric, currency = 'USD' }: AgeDistributionBarProps) => {
  const chartData = useMemo(() => {
    const byAge: Record<string, { male: number; female: number }> = {};
    for (const row of data) {
      const g = row.gender.toLowerCase();
      const entry = byAge[row.ageRange] ?? (byAge[row.ageRange] = { male: 0, female: 0 });
      if (g === 'male') entry.male += Number(row[metric] ?? 0);
      else if (g === 'female') entry.female += Number(row[metric] ?? 0);
    }
    return AGE_ORDER.filter((age) => byAge[age]).map((age) => ({
      age,
      Male: byAge[age]?.male ?? 0,
      Female: byAge[age]?.female ?? 0,
    }));
  }, [data, metric]);

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
          dataKey="age"
          tick={{ fill: 'var(--color-text-primary)', fontSize: 13 }}
        />
        <YAxisComponent
          tick={{ fill: 'var(--color-text-muted)', fontSize: 12 }}
        />
        <TooltipComponent {...tooltipProps} />
        <BarComponent
          dataKey="Male"
          stackId="gender"
          fill={MALE_COLOR}
          radius={[0, 0, 0, 0]}
        />
        <BarComponent
          dataKey="Female"
          stackId="gender"
          fill={FEMALE_COLOR}
          radius={[chartTheme.cornerRadius / 2, chartTheme.cornerRadius / 2, 0, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  );
};

export default AgeDistributionBar;
