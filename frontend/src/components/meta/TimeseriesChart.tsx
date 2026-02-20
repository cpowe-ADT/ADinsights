import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ComponentType } from 'react';

import { formatNumber } from '../../lib/format';
import type { MetaTimeseriesPoint } from '../../lib/metaPageInsights';

type TimeseriesChartProps = {
  title: string;
  points: MetaTimeseriesPoint[];
};

const TimeseriesChart = ({ title, points }: TimeseriesChartProps) => {
  const data = points.map((point) => ({
    end_time: point.end_time.slice(0, 10),
    value: point.value ? Number(point.value) : 0,
  }));

  const GridComponent = CartesianGrid as unknown as ComponentType<Record<string, unknown>>;
  const XAxisComponent = XAxis as unknown as ComponentType<Record<string, unknown>>;
  const YAxisComponent = YAxis as unknown as ComponentType<Record<string, unknown>>;
  const TooltipComponent = Tooltip as unknown as ComponentType<Record<string, unknown>>;
  const LineComponent = Line as unknown as ComponentType<Record<string, unknown>>;

  return (
    <article className="panel meta-timeseries-card">
      <h3>{title}</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <GridComponent strokeDasharray="3 3" />
          <XAxisComponent dataKey="end_time" />
          <YAxisComponent tickFormatter={(value: number) => formatNumber(value)} />
          <TooltipComponent />
          <LineComponent type="monotone" dataKey="value" stroke="#0f766e" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </article>
  );
};

export default TimeseriesChart;
