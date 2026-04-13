import { useMemo } from 'react';
import type { ComponentType } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import type { AgeGenderBreakdown } from '../state/useDashboardStore';
import { chartMargins, chartPalette, chartTheme, createTooltipProps } from '../styles/chartTheme';
import { formatNumber } from '../lib/format';

const AGE_ORDER = ['13-17', '18-24', '25-34', '35-44', '45-54', '55-64', '65+'];
const MALE_COLOR = chartPalette[0];
const FEMALE_COLOR = chartPalette[1];

interface AgeGenderPyramidProps {
  data: AgeGenderBreakdown[];
  metric?: 'impressions' | 'reach' | 'clicks' | 'spend';
}

const AgeGenderPyramid = ({ data, metric = 'impressions' }: AgeGenderPyramidProps) => {
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
      male: -(byAge[age]?.male ?? 0),
      female: byAge[age]?.female ?? 0,
    }));
  }, [data, metric]);

  const tooltipProps = useMemo(
    () => createTooltipProps({
      valueType: 'number',
      valueFormatter: (v) => formatNumber(Math.abs(Number(v))),
    }),
    [],
  );

  const BarComponent = Bar as unknown as ComponentType<Record<string, unknown>>;
  const GridComponent = CartesianGrid as unknown as ComponentType<Record<string, unknown>>;
  const XAxisComponent = XAxis as unknown as ComponentType<Record<string, unknown>>;
  const YAxisComponent = YAxis as unknown as ComponentType<Record<string, unknown>>;
  const TooltipComponent = Tooltip as unknown as ComponentType<Record<string, unknown>>;

  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={chartData} layout="vertical" margin={{ ...chartMargins, left: 48 }}>
        <GridComponent
          horizontal={false}
          stroke={chartTheme.grid.stroke}
          strokeDasharray={chartTheme.grid.strokeDasharray}
        />
        <XAxisComponent
          type="number"
          tickFormatter={(v: number) => formatNumber(Math.abs(v))}
          tick={{ fill: 'var(--color-text-muted)', fontSize: 12 }}
        />
        <YAxisComponent
          type="category"
          dataKey="age"
          width={44}
          tick={{ fill: 'var(--color-text-primary)', fontSize: 13 }}
        />
        <TooltipComponent {...tooltipProps} />
        <BarComponent
          dataKey="male"
          name="Male"
          fill={MALE_COLOR}
          radius={[chartTheme.cornerRadius / 2, 0, 0, chartTheme.cornerRadius / 2]}
          stackId="pyramid"
        />
        <BarComponent
          dataKey="female"
          name="Female"
          fill={FEMALE_COLOR}
          radius={[0, chartTheme.cornerRadius / 2, chartTheme.cornerRadius / 2, 0]}
          stackId="pyramid"
        />
      </BarChart>
    </ResponsiveContainer>
  );
};

export default AgeGenderPyramid;
