import { useMemo } from 'react';
import type { ComponentType } from 'react';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import type { GenderBreakdown } from '../state/useDashboardStore';
import { chartPalette } from '../styles/chartTheme';
import { formatNumber } from '../lib/format';

const GENDER_COLORS: Record<string, string> = {
  male: chartPalette[0],
  female: chartPalette[1],
  unknown: chartPalette[4],
};

const GENDER_LABELS: Record<string, string> = {
  male: 'Male',
  female: 'Female',
  unknown: 'Unknown',
};

interface GenderDonutProps {
  data: GenderBreakdown[];
  metric?: 'impressions' | 'reach' | 'clicks' | 'spend';
}

const GenderDonut = ({ data, metric = 'impressions' }: GenderDonutProps) => {
  const chartData = useMemo(
    () =>
      data.map((row) => ({
        name: GENDER_LABELS[row.gender.toLowerCase()] ?? row.gender,
        value: Number(row[metric] ?? 0),
        gender: row.gender.toLowerCase(),
      })),
    [data, metric],
  );

  const total = useMemo(() => chartData.reduce((sum, r) => sum + r.value, 0), [chartData]);

  const PieComponent = Pie as unknown as ComponentType<Record<string, unknown>>;
  const TooltipComponent = Tooltip as unknown as ComponentType<Record<string, unknown>>;

  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <PieComponent
          data={chartData}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={100}
          paddingAngle={2}
        >
          {chartData.map((entry) => (
            <Cell key={entry.gender} fill={GENDER_COLORS[entry.gender] ?? chartPalette[3]} />
          ))}
        </PieComponent>
        <TooltipComponent
          contentStyle={{
            backgroundColor: '#0f172a',
            color: '#f8fafc',
            borderRadius: 8,
            border: '1px solid rgba(148, 163, 184, 0.35)',
          }}
          formatter={(value: number) => formatNumber(value)}
        />
        <text
          x="50%"
          y="50%"
          textAnchor="middle"
          dominantBaseline="middle"
          fill="var(--color-text-primary)"
          fontSize={16}
          fontWeight={600}
        >
          {formatNumber(total)}
        </text>
      </PieChart>
    </ResponsiveContainer>
  );
};

export default GenderDonut;
