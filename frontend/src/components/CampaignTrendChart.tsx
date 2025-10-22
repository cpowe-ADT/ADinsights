import { Area, AreaChart, CartesianGrid, Tooltip, XAxis, YAxis } from 'recharts';

import type { CampaignTrendPoint } from '../state/useDashboardStore';
import {
  axisTickFormatter,
  chartMargins,
  chartPalette,
  chartTheme,
  createTooltipProps,
} from '../styles/chartTheme';

interface CampaignTrendChartProps {
  data: CampaignTrendPoint[];
  currency: string;
}

const dateFormatter = new Intl.DateTimeFormat('en-JM', { month: 'short', day: 'numeric' });

const formatDateLabel = (value: string | number): string => {
  const parsed = new Date(`${value}`);
  if (Number.isNaN(parsed.getTime())) {
    return `${value}`;
  }
  return dateFormatter.format(parsed);
};

const CampaignTrendChart = ({ data, currency }: CampaignTrendChartProps) => {
  const tooltipProps = createTooltipProps({
    valueType: 'currency',
    currency,
    labelFormatter: (value) => formatDateLabel(String(value)),
  });

  return (
    <AreaChart data={data} margin={chartMargins}>
      <defs>
        <linearGradient id="spendAreaGradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={chartPalette[0]} stopOpacity={0.28} />
          <stop offset="100%" stopColor={chartPalette[0]} stopOpacity={0.04} />
        </linearGradient>
      </defs>
      <CartesianGrid
        stroke={chartTheme.grid.stroke}
        strokeDasharray={chartTheme.grid.strokeDasharray}
        vertical={false}
      />
      <XAxis
        dataKey="date"
        axisLine={false}
        tickLine={false}
        tickMargin={12}
        tickFormatter={(value) => formatDateLabel(value)}
      />
      <YAxis
        axisLine={false}
        tickLine={false}
        tickFormatter={(value) => axisTickFormatter(value)}
        width={68}
        domain={[0, 'auto']}
      />
      <Tooltip {...tooltipProps} />
      <Area
        type="monotone"
        dataKey="spend"
        stroke={chartPalette[0]}
        strokeWidth={2}
        fill="url(#spendAreaGradient)"
        dot={{ r: chartTheme.point.radius, strokeWidth: 0, fill: chartPalette[0] }}
        activeDot={{ r: chartTheme.point.activeRadius }}
      />
    </AreaChart>
  );
};

export default CampaignTrendChart;
