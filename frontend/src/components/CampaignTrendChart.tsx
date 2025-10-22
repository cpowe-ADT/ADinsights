import type { ComponentType } from 'react';
import { Area, AreaChart, CartesianGrid, Tooltip, XAxis, YAxis } from 'recharts';

import type { CampaignTrendPoint } from '../state/useDashboardStore';
import {
  axisTickFormatter,
  chartMargins,
  chartPalette,
  chartTheme,
  createTooltipProps,
} from '../styles/chartTheme';

const CartesianGridComponent = CartesianGrid as unknown as ComponentType<any>;
const XAxisComponent = XAxis as unknown as ComponentType<any>;
const YAxisComponent = YAxis as unknown as ComponentType<any>;
const TooltipComponent = Tooltip as unknown as ComponentType<any>;
const AreaComponent = Area as unknown as ComponentType<any>;

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

  const chart =
    // @ts-expect-error - Recharts' component types are incompatible with strict JSX element checks
    <AreaChart data={data} margin={chartMargins}>
      <defs>
        <linearGradient id="spendAreaGradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={chartPalette[0]} stopOpacity={0.28} />
          <stop offset="100%" stopColor={chartPalette[0]} stopOpacity={0.04} />
        </linearGradient>
      </defs>
      <CartesianGridComponent
        stroke={chartTheme.grid.stroke}
        strokeDasharray={chartTheme.grid.strokeDasharray}
        vertical={false}
      />
      <XAxisComponent
        dataKey="date"
        axisLine={false}
        tickLine={false}
        tickMargin={12}
        tickFormatter={(value: string | number) => formatDateLabel(value)}
      />
      <YAxisComponent
        axisLine={false}
        tickLine={false}
        tickFormatter={(value: number) => axisTickFormatter(value)}
        width={68}
        domain={[0, 'auto']}
      />
      <TooltipComponent {...tooltipProps} />
      <AreaComponent
        type="monotone"
        dataKey="spend"
        stroke={chartPalette[0]}
        strokeWidth={2}
        fill="url(#spendAreaGradient)"
        dot={{ r: chartTheme.point.radius, strokeWidth: 0, fill: chartPalette[0] }}
        activeDot={{ r: chartTheme.point.activeRadius }}
      />
    </AreaChart>;

  return chart;
};

export default CampaignTrendChart;
