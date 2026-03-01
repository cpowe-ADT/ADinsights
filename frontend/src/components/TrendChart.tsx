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

type TrendPoint = {
  date: string;
  value: number | null;
};

type TrendChartProps = {
  title: string;
  points: TrendPoint[];
};

const TrendChart = ({ title, points }: TrendChartProps) => {
  const GridComponent = CartesianGrid as unknown as ComponentType<Record<string, unknown>>;
  const XAxisComponent = XAxis as unknown as ComponentType<Record<string, unknown>>;
  const YAxisComponent = YAxis as unknown as ComponentType<Record<string, unknown>>;
  const TooltipComponent = Tooltip as unknown as ComponentType<Record<string, unknown>>;
  const LineComponent = Line as unknown as ComponentType<Record<string, unknown>>;

  return (
    <article className="panel meta-trend-panel" aria-label={title}>
      <h3>{title}</h3>
      <div style={{ width: '100%', height: 280 }}>
        <ResponsiveContainer>
          <LineChart data={points}>
            <GridComponent strokeDasharray="3 3" />
            <XAxisComponent dataKey="date" />
            <YAxisComponent />
            <TooltipComponent />
            <LineComponent type="monotone" dataKey="value" stroke="#1f8a70" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </article>
  );
};

export default TrendChart;
